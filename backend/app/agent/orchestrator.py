import os
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

import anthropic

from app.agent.prompts import SYSTEM_PROMPT
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
    Uses Anthropic Claude API with Tool Use when ANTHROPIC_API_KEY is available,
    or internal deterministic tool execution engine as fallback.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            return await _run_claude_tool_workflow(message, citizen_id, db, api_key)
        except Exception as e:
            logger.warning(f"Claude API call failed: {e}. Falling back to internal engine.")

    return await _run_fallback_tool_workflow(message, citizen_id, db)


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
        return await tool_extract_document_data(db, doc_id)
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


async def _run_claude_tool_workflow(
    message: str,
    citizen_id: str,
    db: AsyncSession,
    api_key: str
) -> Dict[str, Any]:
    client = anthropic.AsyncAnthropic(api_key=api_key)
    messages = [{"role": "user", "content": message}]

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=TOOLS_SCHEMA,
        messages=messages,
    )

    created_app_info = None
    service_reqs = None
    target_service_code = None

    while response.stop_reason == "tool_use":
        tool_results = []
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        for block in assistant_content:
            if block.type == "tool_use":
                t_name = block.name
                t_args = block.input
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

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(t_result)
                })

        messages.append({"role": "user", "content": tool_results})
        print(f"DEBUG: sending to LLM. created_app_info={created_app_info}")

        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,
            messages=messages,
        )

    reply_text = ""
    for block in response.content:
        if block.type == "text":
            reply_text += block.text

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
    db: AsyncSession
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

    # Step 5: Create application if not created yet
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
