import os
import json
import logging
from typing import Dict, Any, List, Optional
import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Application, Document, User, CitizenProfile, ChatMessage
from app.audit import log_audit_event
from app.service_rules import (
    get_requirements as get_rules_requirements,
    get_alternative_documents,
    get_responsible_officer,
    evaluate_citizen_readiness,
    is_requirement_satisfied
)
from app.nlp.normalizer import normalize_text, NormalizationResult
from app.nlp.matcher import match_intent_and_service, Intent, IntentMatchResult
from app.nlp.pii import mask_pii, sanitize_audit_details
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
    1. Normalizes input (typo correction, spelling, abbreviations) without mutating semantics.
    2. Identifies intent, service match, jurisdiction, and conversational context.
    3. Grounds all government requirements in authoritative service rules.
    4. Executes with Gemini API (grounded with pre-retrieved facts) or deterministic engine as fallback.
    5. Mask PII (Aadhaar, PAN, phone) before persisting to ChatMessage and AuditLog.
    """
    from app.config import settings
    api_key = settings.GEMINI_API_KEY
    model_name = settings.GEMINI_MODEL

    # Step 1: Text normalization and typo correction
    norm_result = normalize_text(message)
    original_message = message
    normalized_message = norm_result.normalized_text
    corrections = norm_result.corrections

    # Step 2: Fetch existing application context for this citizen
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
    active_apps = list(active_apps_result.scalars().all())

    # Step 3: Match intent, service, and jurisdiction
    active_service_codes = [a.service.code for a in active_apps] if active_apps else []
    match_result = match_intent_and_service(
        norm_result,
        has_active_apps=bool(active_apps),
        active_service_codes=active_service_codes
    )

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

    result: Dict[str, Any]
    if api_key:
        try:
            result = await _run_gemini_tool_workflow(
                normalized_message, match_result, citizen_id, db, api_key, model_name, app_context_str
            )
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Falling back to internal engine.")
            result = await _run_fallback_tool_workflow(
                norm_result=norm_result,
                match_result=match_result,
                citizen_id=citizen_id,
                db=db,
                active_apps=active_apps
            )
    else:
        result = await _run_fallback_tool_workflow(
            norm_result=norm_result,
            match_result=match_result,
            citizen_id=citizen_id,
            db=db,
            active_apps=active_apps
        )

    # Attach NLU metadata to response
    result["detected_intent"] = match_result.intent
    result["normalized_message"] = normalized_message
    if corrections:
        result["corrections"] = corrections

    # Step 4: PII-Protected Audit & Conversation Persistence
    try:
        app_uuid = None
        if result.get("application_id"):
            try:
                app_uuid = uuid.UUID(str(result["application_id"]))
            except ValueError:
                pass

        user_uuid = uuid.UUID(citizen_id)

        # Mask PII (Aadhaar, PAN, phone numbers) before persistence
        masked_original = mask_pii(original_message)
        masked_normalized = mask_pii(normalized_message)

        # Store citizen message with PII masked
        citizen_chat = ChatMessage(
            user_id=user_uuid,
            application_id=app_uuid,
            role="user",
            original_message=masked_original,
            normalized_message=masked_normalized,
            intent=match_result.intent,
            service_code=result.get("service_code") or match_result.service_code,
            corrections=corrections if corrections else None,
            reply=None
        )
        db.add(citizen_chat)

        # Store AI response
        ai_chat = ChatMessage(
            user_id=user_uuid,
            application_id=app_uuid,
            role="assistant",
            original_message=result.get("reply", ""),
            normalized_message=None,
            intent=match_result.intent,
            service_code=result.get("service_code") or match_result.service_code,
            corrections=None,
            reply=result.get("reply", "")
        )
        db.add(ai_chat)

        # Log audit entry with sanitized details
        audit_details = sanitize_audit_details({
            "original_message": masked_original,
            "normalized_message": masked_normalized,
            "corrections": corrections,
            "intent": match_result.intent,
            "service_code": result.get("service_code") or match_result.service_code,
        })

        await log_audit_event(
            db=db,
            actor_type="CITIZEN",
            action="CHAT_MESSAGE",
            resource_type="chat",
            user_id=user_uuid,
            resource_id=str(app_uuid) if app_uuid else None,
            details=audit_details
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to persist chat audit: {e}")

    return result


async def _execute_tool(tool_name: str, tool_args: dict, citizen_id: str, db: AsyncSession) -> Dict[str, Any]:
    """Executes backend tool calls validated against database."""
    from app.events import notifier

    activity_map = {
        "list_services": "Checking available services...",
        "get_service_requirements": "Checking authoritative service requirements...",
        "create_application": "Preparing your application...",
        "extract_document_data": "Extracting information from your document...",
        "get_citizen_profile": "Checking your verified profile...",
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
    match_result: IntentMatchResult,
    citizen_id: str,
    db: AsyncSession,
    api_key: str,
    model_name: str,
    app_context_str: str = ""
) -> Dict[str, Any]:
    """
    Executes Gemini workflow strictly grounded in deterministically pre-retrieved rules.
    Prevents the LLM from inventing government document requirements.
    """
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

    # Deterministic Pre-Retrieval Grounding
    target_service_code = match_result.service_code
    jurisdiction_requested = match_result.entities.get("jurisdiction")
    grounding_str = ""
    service_reqs = None

    if target_service_code:
        rules_info = await get_rules_requirements(target_service_code, jurisdiction=jurisdiction_requested, db=db)
        if rules_info.get("jurisdiction_supported", True):
            service_reqs = rules_info
            grounding_str = (
                f"\n\nAUTHORITATIVE RULES (Source-Backed, do not alter or add requirements):\n"
                f"- Service: {rules_info['service_name']} (Department: {rules_info['department']})\n"
                f"- Required Documents: {rules_info['required_documents']}\n"
                f"- Required Fields: {rules_info['required_fields']}\n"
                f"- Dependencies: {rules_info.get('document_dependencies')}\n"
                f"- Responsible Authority: {rules_info.get('responsible_authority')}\n"
                f"- Processing Time: {rules_info.get('processing_time_days')} days | Fee: ₹{rules_info.get('fee_amount')}\n"
            )
        else:
            grounding_str = (
                f"\n\nJURISDICTION NOTICE: Official requirements for requested jurisdiction '{rules_info.get('requested_jurisdiction')}' "
                f"are NOT verified in SEVA. Inform the user clearly that requirements cannot be verified. Supported: {rules_info.get('supported_jurisdictions')}."
            )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + app_context_str + grounding_str,
        tools=[gemini_tool],
        temperature=0.1
    )

    messages = [
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    ]

    created_app_info = None

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
        messages.append(types.Content(role="model", parts=response.candidates[0].content.parts))

        function_responses = []
        for fc in response.function_calls:
            t_name = fc.name
            t_args = fc.args

            if t_name in ["create_application", "get_citizen_profile"]:
                t_args["citizen_id"] = citizen_id

            t_result = await _execute_tool(t_name, t_args, citizen_id, db)

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
    norm_result: NormalizationResult,
    match_result: IntentMatchResult,
    citizen_id: str,
    db: AsyncSession,
    active_apps: List[Application] = []
) -> Dict[str, Any]:
    """
    Deterministic language understanding & service rules grounding engine.
    Ensures exact compliance without speculating on government facts.
    """
    text = norm_result.normalized_text.lower().strip()
    target_service_code = match_result.service_code
    jurisdiction_requested = match_result.entities.get("jurisdiction")

    # 1. Filter active apps if user specified explicit SEVA references
    explicit_refs = re.findall(r"\bseva-\d+\b", norm_result.original_text.lower())
    if not explicit_refs:
        explicit_refs = re.findall(r"\bseva-\d+\b", text)

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
        if matching_apps:
            active_apps = matching_apps

    # 2. Check info request for an existing application (e.g., 'What documents are required for an Income Certificate?')
    is_general_info_query = any(k in text for k in [
        "what documents are required", "what are the requirements",
        "which documents are required", "what papers are needed", "requirements for"
    ])
    if is_general_info_query and len(active_apps) == 1 and target_service_code == active_apps[0].service.code:
        app = active_apps[0]
        reqs = await get_rules_requirements(app.service.code, jurisdiction=jurisdiction_requested, db=db)
        docs_list = "\n".join([f"  • {d.replace('_', ' ').title()}" for d in reqs["required_documents"]])
        fields_list = "\n".join([f"  • {f.replace('_', ' ').title()}" for f in reqs["required_fields"]])
        reply = (
            f"Here are the official requirements for **{reqs['service_name']}** (Department of {reqs['department'].title()}):\n\n"
            f"📋 **Required Documents:**\n{docs_list}\n\n"
            f"📝 **Required Information:**\n{fields_list}\n\n"
            f"Your active application reference is `{app.application_number}` (Status: `{app.status}`)."
        )
        return {
            "reply": reply,
            "application_id": str(app.id),
            "service_code": app.service.code,
            "status": app.status,
            "required_documents": reqs["required_documents"],
            "required_fields": reqs["required_fields"],
        }

    # 3. Disambiguate multiple active apps when submitting/preparing
    if len(active_apps) > 1 and match_result.intent == Intent.PREPARE_OR_SUBMIT and not explicit_refs:
        titles = ", ".join([f"{a.service.title} ({a.application_number})" for a in active_apps])
        return {
            "reply": f"You have multiple active applications: {titles}. Could you please specify which application you are referring to?",
            "application_id": None,
            "service_code": None,
            "status": None,
            "required_documents": [],
            "required_fields": [],
        }

    # 4. Handle single active app ready for consent/submission
    if len(active_apps) == 1 and match_result.intent == Intent.PREPARE_OR_SUBMIT:
        app = active_apps[0]
        if app.status == "READY_FOR_REVIEW":
            consent_res = await _execute_tool("request_consent", {
                "application_id": str(app.id),
                "data_requested": [],
                "requesting_department": app.service.department,
                "purpose": "Application Processing"
            }, citizen_id, db)
            return {
                "reply": "I have prepared your application for submission. Please review and approve the consent request.",
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

    # 5. Handle "how can i prove my family income" / "where do i get income proof"
    if any(k in text for k in ["prove my family income", "prove family income", "where do i get income proof", "where do i get income"]):
        rules = await get_rules_requirements("income_certificate", jurisdiction=jurisdiction_requested, db=db)
        income_options = rules.get("document_options", {}).get("income_proof", [])
        opts_formatted = "\n".join([f"  • **{opt['name']}** (Authority: *{opt['authority']}*)" for opt in income_options])
        authority = rules.get("responsible_authority", {})
        
        reply = (
            f"To prove family income for an official **{rules['service_name']}**, government revenue rules recognize the following source-backed proofs:\n\n"
            f"{opts_formatted}\n\n"
            f"🏛️ **Responsible Authority:** {authority.get('title', 'Tahsildar')}, {authority.get('office', 'Taluk Office')}.\n"
            f"ℹ️ *You can obtain salary slips from your employer, Form 16/ITR from the Income Tax portal, or an income affidavit from a notary or Executive Magistrate.*"
        )
        matched_app_id = str(active_apps[0].id) if active_apps and active_apps[0].service.code == "income_certificate" else None
        return {
            "reply": reply,
            "application_id": matched_app_id,
            "service_code": "income_certificate",
            "status": active_apps[0].status if matched_app_id else None,
            "required_documents": rules["required_documents"],
            "required_fields": rules["required_fields"],
        }

    # 6. Check for Unsupported Jurisdiction (Eliminating silent fallback)
    if target_service_code and jurisdiction_requested:
        rules = await get_rules_requirements(target_service_code, jurisdiction=jurisdiction_requested, db=db)
        if not rules.get("jurisdiction_supported", True):
            supported_str = ", ".join(rules.get("supported_jurisdictions", ["Karnataka", "Maharashtra", "Delhi"]))
            reply = (
                f"⚠️ **Jurisdiction Notice**: We currently do not have verified official rules for **{jurisdiction_requested.title()}** for this service.\n\n"
                f"SEVA currently supports verified rules for: **{supported_str}**.\n\n"
                "Please select a supported state or proceed using national standard requirements."
            )
            return {
                "reply": reply,
                "application_id": None,
                "service_code": target_service_code,
                "status": None,
                "required_documents": [],
                "required_fields": [],
                "jurisdiction": {"supported": False, "requested": jurisdiction_requested}
            }

    # 7. Handle "i already uploaded my id" / Document Upload Follow-up
    if match_result.intent == Intent.DOCUMENT_UPLOADED_FOLLOWUP:
        profile_data = await _execute_tool("get_citizen_profile", {"citizen_id": citizen_id}, citizen_id, db)
        uploaded_docs = profile_data.get("uploaded_document_types", [])
        
        target_app = active_apps[0] if active_apps else None
        target_code = target_service_code or (target_app.service.code if target_app else "income_certificate")
        rules = await get_rules_requirements(target_code, jurisdiction=jurisdiction_requested, db=db)
        
        missing_docs = [d for d in rules["required_documents"] if not is_requirement_satisfied(d, uploaded_docs)]
        verified_items = [d.replace('_', ' ').title() for d in uploaded_docs]
        verified_str = ", ".join(verified_items) if verified_items else "Identity proof"
        
        if missing_docs:
            missing_formatted = "\n".join([f"  • {d.replace('_', ' ').title()}" for d in missing_docs])
            reply = (
                f"✅ I have recorded your verified document(s): **{verified_str}**.\n\n"
                f"To complete your **{rules['service_name']}** application, we still require:\n"
                f"{missing_formatted}\n\n"
                f"Please upload the remaining document(s) to proceed."
            )
        else:
            reply = (
                f"✅ All required documents for **{rules['service_name']}** have been uploaded and verified!\n\n"
                f"Your application is ready for review. You can tell me 'Please prepare my application' to proceed to submission."
            )

        return {
            "reply": reply,
            "application_id": str(target_app.id) if target_app else None,
            "service_code": target_code,
            "status": target_app.status if target_app else "COLLECTING_DOCUMENTS",
            "required_documents": missing_docs,
            "required_fields": rules["required_fields"],
        }

    # 8. Handle "what am i missing?"
    if match_result.intent == Intent.CHECK_STATUS_OR_MISSING:
        if active_apps:
            app = active_apps[0]
            profile_data = await _execute_tool("get_citizen_profile", {"citizen_id": citizen_id}, citizen_id, db)
            merged_profile = profile_data.get("merged_profile", {})
            uploaded_docs = profile_data.get("uploaded_document_types", [])

            readiness = await evaluate_citizen_readiness(app.service.code, uploaded_docs, merged_profile, jurisdiction=jurisdiction_requested, db=db)
            missing_docs = readiness["missing_documents"]
            missing_fields = readiness["missing_fields"]

            docs_formatted = "\n".join([f"  • {d.replace('_', ' ').title()}" for d in missing_docs]) if missing_docs else "  • All required documents verified! ✅"
            fields_formatted = "\n".join([f"  • {f.replace('_', ' ').title()}" for f in missing_fields]) if missing_fields else "  • All required fields completed! ✅"

            reply = (
                f"Here is the status breakdown for your **{readiness['service_name']}** application (`{app.application_number}`):\n\n"
                f"📋 **Missing Documents:**\n{docs_formatted}\n\n"
                f"📝 **Missing Information:**\n{fields_formatted}\n\n"
                f"**Current Status:** `{app.status}`"
            )
            return {
                "reply": reply,
                "application_id": str(app.id),
                "service_code": app.service.code,
                "status": app.status,
                "required_documents": missing_docs,
                "required_fields": missing_fields,
            }

    # 9. Handle service requirements query (e.g. "what papers do i need", "what documents are required")
    if match_result.intent == Intent.CHECK_REQUIREMENTS:
        req_service_code = target_service_code or (active_apps[-1].service.code if active_apps else None)
        if req_service_code:
            rules = await get_rules_requirements(req_service_code, jurisdiction=jurisdiction_requested, db=db)
            docs_list = "\n".join([f"  • {d.replace('_', ' ').title()}" for d in rules["required_documents"]])
            fields_list = "\n".join([f"  • {f.replace('_', ' ').title()}" for f in rules["required_fields"]])
            
            matched_app = next((a for a in active_apps if a.service.code == req_service_code), None)
            app_str = f" for your `{matched_app.application_number}` application" if matched_app else ""
            
            reply = (
                f"For an official **{rules['service_name']}** ({rules['department'].title()} Department){app_str}, "
                f"the required government documents and fields according to rules are:\n\n"
                f"📋 **Required Documents:**\n{docs_list}\n\n"
                f"📝 **Required Information:**\n{fields_list}\n\n"
                f"⏱️ Estimated Processing Time: {rules['processing_time_days']} days | Fee: ₹{rules['fee_amount']:.2f}"
            )
            matched_app_id = str(matched_app.id) if matched_app else None
            return {
                "reply": reply,
                "application_id": matched_app_id,
                "service_code": req_service_code,
                "status": matched_app.status if matched_app else None,
                "required_documents": rules["required_documents"],
                "required_fields": rules["required_fields"],
            }

    # 10. Ambiguous intent -> call list_services()
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

    # 11. Service application / initiation
    rules = await get_rules_requirements(target_service_code, jurisdiction=jurisdiction_requested, db=db)
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

    profile_data = await _execute_tool("get_citizen_profile", {"citizen_id": citizen_id}, citizen_id, db)
    merged_profile = profile_data.get("merged_profile", {})
    uploaded_docs = profile_data.get("uploaded_document_types", [])

    all_docs = requirements.get("required_documents", [])
    all_fields = requirements.get("required_fields", [])

    # Check requirement satisfaction with document semantic aliases
    missing_docs = [doc for doc in all_docs if not is_requirement_satisfied(doc, uploaded_docs)]
    missing_fields = [field for field in all_fields if field not in merged_profile]

    # BLOCKER 1 FIX: Search ALL active applications for target service
    matched_app = next((a for a in active_apps if a.service.code == target_service_code), None)
    if matched_app:
        app_result = {
            "application_id": str(matched_app.id),
            "application_number": matched_app.application_number,
            "current_status": matched_app.status,
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

    docs_formatted = "\n".join([f"  • {doc.replace('_', ' ').title()}" for doc in missing_docs]) if missing_docs else "  • All required documents uploaded and verified! ✅"
    fields_formatted = "\n".join([f"  • {field.replace('_', ' ').title()}" for field in missing_fields]) if missing_fields else "  • All required information extracted! ✅"

    verified_summary = ""
    if uploaded_docs:
        verified_items = [d.replace('_', ' ').title() for d in uploaded_docs]
        verified_summary = f"\n\n✅ **Verified Data Already in Profile:**\n" + "\n".join([f"  • {item}" for item in verified_items])

    scholarship_note = ""
    if "scholarship" in text or "scholership" in text:
        scholarship_note = (
            "🎓 *Scholarship Guidance: Government scholarships require an official Income Certificate issued by the Revenue Department "
            "to verify your family's annual income eligibility ceiling.*\n\n"
        )

    newborn_note = ""
    if "newborn" in text or "new born" in text or "baby" in text:
        newborn_note = (
            "👶 *Note: A newborn child's Aadhaar is NOT required for birth registration. "
            "The hospital birth notification and parents' identity proof are the authoritative legal records required.*\n\n"
        )

    authority_info = rules.get("responsible_authority", {})
    office_str = f"🏛️ **Issuing Authority:** {authority_info.get('title', 'Competent Authority')}, {authority_info.get('office', 'Departmental Office')}\n\n"

    reply_text = (
        f"{scholarship_note}{newborn_note}"
        f"I have initialized your application workflow for **{requirements['service_name']}** "
        f"(Department: *{requirements['department'].title()}*).\n\n"
        f"**Application Reference ID:** `{app_result['application_number']}`\n"
        f"**Workflow Status:** `{app_result['current_status']}`{verified_summary}\n\n"
        f"{office_str}"
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
