import os
import json
import logging
from typing import Dict, Any, List, Optional
import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Application
from app.agent.tools import (
    TOOLS_SCHEMA,
    tool_list_services,
    tool_get_service_requirements,
    tool_create_application,
    tool_extract_document_data,
    tool_get_citizen_profile,
    tool_submit_application,
    tool_request_consent,
)

logger = logging.getLogger(__name__)


async def run_agent_workflow(
    message: str,
    citizen_id: str,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Orchestrates the AI agent reasoning and tool execution loop.
    Uses Gemini API with Tool Use when GEMINI_API_KEY is available,
    or internal deterministic tool execution engine as fallback.
    """
    from app.config import settings
    api_key = settings.GEMINI_API_KEY
    model_name = settings.GEMINI_MODEL

    # Fetch existing application context
    active_apps_result = await db.execute(
        select(Application).options(selectinload(Application.service)).where(
            Application.user_id == uuid.UUID(citizen_id),
            Application.status.in_([
                "DISCOVER", "COLLECTING_DOCUMENTS", "EXTRACTING",
                "VALIDATING", "MISSING_INFORMATION", "READY_FOR_REVIEW",
                "CONSENT_REQUIRED", "SUBMITTING", "SUBMITTED", "TRACKING"
            ])
        )
    )
    active_apps = active_apps_result.scalars().all()

    app_context_str = ""
    if active_apps:
        app_context_str = "\n\nCURRENT APPLICATION CONTEXT:\nThe user has the following active/existing applications:\n"
        for app in active_apps:
            app_context_str += (
                f"- Application Reference: {app.application_number} (ID: {app.id})\n"
                f"  Service: {app.service.title} ({app.service.code})\n"
                f"  Status: {app.status}\n"
            )
            if app.government_reference:
                app_context_str += f"  Gov Reference: {app.government_reference}\n"
        app_context_str += "\nUse this context to resolve references to 'my application'."

    if api_key:
        try:
            return await _run_gemini_tool_workflow(message, citizen_id, db, api_key, model_name, app_context_str)
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Falling back to internal engine.")

    return await _run_fallback_tool_workflow(message, citizen_id, db, active_apps)


async def _execute_tool(tool_name: str, tool_args: dict, citizen_id: str, db: AsyncSession) -> Dict[str, Any]:
    """Executes backend tool calls validated against database."""
    from app.events import notifier

    activity_map = {
        "list_services": "Checking available services...",
        "get_service_requirements": "Checking service requirements...",
        "create_application": "Preparing your application...",
        "extract_document_data": "Extracting information from your document...",
        "get_citizen_profile": "Checking your profile...",
        "request_consent": "Preparing your consent request...",
        "submit_application": "Submitting your application..."
    }

    activity = activity_map.get(tool_name, "Processing...")
    app_id = tool_args.get("application_id", "")

    notifier.broadcast(
        user_id=citizen_id,
        event="AGENT_ACTIVITY",
        application_id=app_id,
        data={"activity": activity}
    )

    if tool_name == "list_services":
        return {"services": await tool_list_services(db)}
    elif tool_name == "get_service_requirements":
        code = tool_args.get("service_code")
        return await tool_get_service_requirements(db, code)
    elif tool_name == "create_application":
        code = tool_args.get("service_code")
        return await tool_create_application(db, code, citizen_id)
    elif tool_name == "extract_document_data":
        doc_id = tool_args.get("document_id")
        return await tool_extract_document_data(db, doc_id, citizen_id)
    elif tool_name == "get_citizen_profile":
        return await tool_get_citizen_profile(db, citizen_id)
    elif tool_name == "request_consent":
        app_id = tool_args.get("application_id")
        data_req = tool_args.get("data_requested")
        req_dep = tool_args.get("requesting_department")
        purpose = tool_args.get("purpose")
        return await tool_request_consent(db, app_id, data_req, req_dep, purpose)
    elif tool_name == "submit_application":
        app_id = tool_args.get("application_id")
        return await tool_submit_application(db, app_id)
    else:
        return {"error": f"Unknown tool '{tool_name}'"}


async def _run_gemini_tool_workflow(
    message: str,
    citizen_id: str,
    db: AsyncSession,
    api_key: str,
    model_name: str,
    app_context_str: str = ""
) -> Dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    def map_type(t: str) -> str:
        mapping = {
            "string": "STRING",
            "object": "OBJECT",
            "array": "ARRAY",
            "boolean": "BOOLEAN",
            "integer": "INTEGER",
            "number": "NUMBER"
        }
        return mapping.get(t.lower(), "STRING")

    def convert_schema(schema: dict):
        if not schema:
            return None
        res = {}
        if "type" in schema:
            res["type"] = map_type(schema["type"])
        if "description" in schema:
            res["description"] = schema["description"]
        if "properties" in schema:
            res["properties"] = {k: convert_schema(v) for k, v in schema["properties"].items()}
        if "items" in schema:
            res["items"] = convert_schema(schema["items"])
        if "required" in schema:
            res["required"] = schema["required"]
        return res

    declarations = []
    for t in TOOLS_SCHEMA:
        decl = types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=convert_schema(t["input_schema"])
        )
        declarations.append(decl)

    gemini_tool = types.Tool(function_declarations=declarations)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + app_context_str,
        tools=[gemini_tool],
        temperature=0.2
    )

    messages = [
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    ]

    created_app_info = None
    service_reqs = None
    target_service_code = None

    from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
    from google.genai.errors import APIError

    def is_transient_error(e):
        if isinstance(e, APIError):
            if e.code in [429, 500, 502, 503, 504]:
                return True
        return False

    @retry(
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(6),
        retry=retry_if_exception(is_transient_error),
        reraise=True
    )
    async def call_gemini():
        return await client.aio.models.generate_content(
            model=model_name,
            contents=messages,
            config=config
        )

    response = await call_gemini()

    while response.function_calls:
        # Append the model's response to history
        # Function calls are returned as parts in the model's response
        messages.append(types.Content(role="model", parts=response.candidates[0].content.parts))

        function_responses = []
        for fc in response.function_calls:
            t_name = fc.name
            t_args = fc.args

            if t_name in ["create_application", "get_citizen_profile"]:
                t_args["citizen_id"] = citizen_id

            t_result = await _execute_tool(t_name, t_args, citizen_id, db)
            print(f"DEBUG: tool {t_name} returned {t_result}")

            if isinstance(t_result, dict):
                if "application_id" in t_result or "current_status" in t_result:
                    if created_app_info is None:
                        created_app_info = {}
                    if "application_id" in t_result:
                        created_app_info["application_id"] = t_result["application_id"]
                    if "current_status" in t_result:
                        created_app_info["current_status"] = t_result["current_status"]
                    if "service_code" in t_result:
                        target_service_code = t_result.get("service_code")

            if t_name == "get_service_requirements" and "service_code" in t_result:
                service_reqs = t_result
                target_service_code = t_result.get("service_code")

            function_responses.append(
                types.Part.from_function_response(
                    name=t_name,
                    response=t_result
                )
            )

        messages.append(types.Content(role="user", parts=function_responses))
        print(f"DEBUG: sending to LLM. created_app_info={created_app_info}")

        response = await call_gemini()

    reply_text = response.text if response.text else ""

    return {
        "reply": reply_text,
        "application_id": created_app_info.get("application_id") if created_app_info else None,
        "service_code": target_service_code,
        "status": created_app_info.get("current_status") if created_app_info else None,
        "required_documents": service_reqs.get("required_documents", []) if service_reqs else [],
        "required_fields": service_reqs.get("required_fields", []) if service_reqs else [],
    }


async def _run_fallback_tool_workflow(
    message: str,
    citizen_id: str,
    db: AsyncSession,
    active_apps: List[Application] = []
) -> Dict[str, Any]:
    msg_lower = message.strip().lower()

    # Step 1: Detect intent
    target_service_code: Optional[str] = None
    if "driving" in msg_lower or "licence" in msg_lower or "license" in msg_lower:
        target_service_code = "driving_license"
    elif "income" in msg_lower:
        target_service_code = "income_certificate"
    elif "birth" in msg_lower:
        target_service_code = "birth_certificate"

    # Filter active apps if user specified explicit SEVA references
    explicit_refs = re.findall(r"\bseva-\d+\b", msg_lower)
    if explicit_refs:
        if len(explicit_refs) > 1:
            return {
                "reply": "You mentioned multiple application numbers. Could you please specify which one you want to proceed with?",
                "application_id": None,
                "service_code": None,
                "status": None,
                "required_documents": [],
                "required_fields": [],
            }

        explicit_ref = explicit_refs[0].upper()
        matched_app = next((a for a in active_apps if a.application_number == explicit_ref), None)
        if matched_app:
            active_apps = [matched_app]
        else:
            return {
                "reply": f"I couldn't find that application ({explicit_ref}) in your active profile.",
                "application_id": None,
                "service_code": None,
                "status": None,
                "required_documents": [],
                "required_fields": [],
            }
    elif target_service_code:
        # Filter active apps if user specified a service and no explicit SEVA ref
        matching_apps = [a for a in active_apps if a.service.code == target_service_code]
        # Only restrict if it narrows it down
        if matching_apps:
            active_apps = matching_apps

    # Minimal fallback logic for existing applications
    if len(active_apps) > 1 and ("prepare" in msg_lower or "submit" in msg_lower or "ready" in msg_lower or "application" in msg_lower):
        titles = ", ".join([f"{a.service.title} ({a.application_number})" for a in active_apps])
        return {
            "reply": f"You have multiple active applications: {titles}. Could you please specify which application you are referring to?",
            "application_id": None,
            "service_code": None,
            "status": None,
            "required_documents": [],
            "required_fields": [],
        }

    if len(active_apps) == 1 and ("prepare" in msg_lower or "submit" in msg_lower or "ready" in msg_lower or "application" in msg_lower):
        app = active_apps[0]
        if app.status == "READY_FOR_REVIEW":
            consent_res = await _execute_tool("request_consent", {
                "application_id": str(app.id),
                "data_requested": [],
                "requesting_department": app.service.department,
                "purpose": "Application Processing"
            }, citizen_id, db)
            return {
                "reply": f"I have prepared your application for submission. Please review and approve the consent request.",
                "application_id": str(app.id),
                "service_code": app.service.code,
                "status": "CONSENT_REQUIRED",
                "required_documents": [],
                "required_fields": [],
            }
        elif app.status == "CONSENT_REQUIRED":
            return {
                "reply": f"Your application {app.application_number} is waiting for your consent approval. Please approve it.",
                "application_id": str(app.id),
                "service_code": app.service.code,
                "status": app.status,
                "required_documents": [],
                "required_fields": [],
            }

    # Step 2: Ambiguous intent -> call list_services() tool
    if not target_service_code:
        services = (await _execute_tool("list_services", {}, citizen_id, db)).get("services", [])
        titles = ", ".join([f"'{s['title']}' ({s['code']})" for s in services])
        reply = (
            "We offer several official government services on the SEVA AI platform, including: "
            f"{titles}.\n\n"
            "Could you please specify which service you would like to apply for? "
            "(For example: 'I need an Income Certificate', 'I want a Birth Certificate', or 'I need a Driving License')."
        )
        return {
            "reply": reply,
            "application_id": None,
            "service_code": None,
            "status": None,
            "required_documents": [],
            "required_fields": [],
        }

    # Step 3: Fetch service requirements
    requirements = await _execute_tool("get_service_requirements", {"service_code": target_service_code}, citizen_id, db)
    if "error" in requirements:
        return {
            "reply": f"Could not find requirements for '{target_service_code}'.",
            "application_id": None,
            "service_code": None,
            "status": None,
            "required_documents": [],
            "required_fields": [],
        }

    # Step 4: Fetch citizen merged profile & uploaded documents
    profile_data = await _execute_tool("get_citizen_profile", {"citizen_id": citizen_id}, citizen_id, db)
    merged_profile = profile_data.get("merged_profile", {})
    uploaded_docs = profile_data.get("uploaded_document_types", [])

    # Filter out requirements already provided/extracted
    all_docs = requirements.get("required_documents", [])
    all_fields = requirements.get("required_fields", [])

    missing_docs = [doc for doc in all_docs if doc not in uploaded_docs]
    missing_fields = [field for field in all_fields if field not in merged_profile]

    # Step 5: Create application if not created yet, otherwise reuse
    if len(active_apps) > 0:
        app_result = {
            "application_id": str(active_apps[0].id),
            "application_number": active_apps[0].application_number,
            "current_status": active_apps[0].status,
        }
    else:
        app_result = await _execute_tool("create_application", {"service_code": target_service_code, "citizen_id": citizen_id}, citizen_id, db)
        if "error" in app_result:
            return {
                "reply": f"Application creation failed: {app_result['error']}",
                "application_id": None,
                "service_code": target_service_code,
                "status": None,
                "required_documents": missing_docs,
                "required_fields": missing_fields,
            }

    # Format helpful output reflecting verified vs missing requirements
    docs_formatted = "\n".join([f"  • {doc.replace('_', ' ').title()}" for doc in missing_docs]) if missing_docs else "  • All required documents uploaded and verified! ✅"
    fields_formatted = "\n".join([f"  • {field.replace('_', ' ').title()}" for field in missing_fields]) if missing_fields else "  • All required information extracted! ✅"

    verified_summary = ""
    if uploaded_docs or merged_profile:
        verified_items = [d.replace('_', ' ').title() for d in uploaded_docs]
        verified_summary = f"\n\n✅ **Verified Data Already in Profile:**\n" + "\n".join([f"  • {item}" for item in verified_items])

    reply_text = (
        f"I have initialized your application workflow for **{requirements['service_name']}** "
        f"(Department: *{requirements['department'].title()}*).\n\n"
        f"**Application Reference ID:** `{app_result['application_number']}`\n"
        f"**Workflow Status:** `DISCOVER`{verified_summary}\n\n"
        f"📋 **Documents Still Needed:**\n{docs_formatted}\n\n"
        f"📝 **Information Still Needed:**\n{fields_formatted}\n\n"
        "ℹ️ *Note: Upload your documents below to auto-verify and complete your application preparation.*"
    )

    return {
        "reply": reply_text,
        "application_id": app_result["application_id"],
        "service_code": target_service_code,
        "status": app_result["current_status"],
        "required_documents": missing_docs,
        "required_fields": missing_fields,
    }
