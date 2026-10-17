"""
بيرسل رسالة العميل للذكاء الاصطناعي، وبيجيب الرد بصيغة جيسون بس ما بيثق فيه ثقة عمياء
 بيفحص الرد ويتأكد إنه منطقي وتابع للقيم المسموحة بالنظام
"""
import json
import logging
import re
from openai import OpenAI
import config
from prompts import SYSTEM_PROMPT, QUESTION_PROMPT, STEPS_PROMPT

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = ["CLASSIFY", "ASK_FOR_INFO", "OUT_OF_SCOPE"]

# آخر سبب لفشل النموذج: (Ticket details) عشان تعرف إذا النموذج شغال أو لا
last_error = ""


def ask_llm(system_prompt, user_prompt, json_mode=True):
    # إرسال الطلب إلى نموذج الذكاء الاصطناعي واستلام الرد
    client = OpenAI(base_url= config.LLM_BASE_URL, api_key=config.LLM_API_KEY, timeout=30)
    args = dict(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=config.LLM_TEMPERATURE,
    )
    try:
        if json_mode:
            completion = client.chat.completions.create(**args, response_format={"type": "json_object"})
        else:
            completion = client.chat.completions.create(**args)
    except Exception:
        if not json_mode:
            raise
        completion = client.chat.completions.create(**args)
    return completion.choices[0].message.content


def parse_json(output):
    # تحويل النص القادم إلى قاموس وتنظيفه (بيشيل <think> والـ ``` وأي كلام حوالين الـ JSON)
    try:
        clean_text = re.sub(r"<think>.*?</think>", "", output, flags=re.S)
        clean_text = clean_text.replace("```json", "").replace("```", "").strip()
        start, end = clean_text.find("{"), clean_text.rfind("}")
        data = json.loads(clean_text[start:end + 1])
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.warning("LLM returned malformed JSON response.")
        return None


def validate_llm_output(data):
    # فلترة وتدقيق إجابة الذكاء الاصطناعي لضمان الأمان
    if not isinstance(data, dict):
        return None

    action = str(data.get("action", "")).strip().upper().replace(" ", "_").replace("-", "_")
    if action == "ASK":
        action = "ASK_FOR_INFO"
    reason = str(data.get("reason", "")).strip()[:200]

    # التحقق من أن القيمة المرجعة ضمن القوائم المسموحة فقط
    if action not in ALLOWED_ACTIONS:
        return None

    #  نقبل الحروف الكبيرة/الصغيرة بالتصنيف
    category = next((c for c in config.CATEGORIES
                     if c.lower() == str(data.get("category", "")).strip().lower()), None)
    if action != "CLASSIFY":
        category = "Other"
    elif category is None:
        return None

    question = str(data.get("question") or data.get("follow_up_question") or "").strip()[:300]
    return {
        "action": action,
        "category": category,
        "reason": reason or "Classified by the AI model.",
        "question": question,                                    # سؤال المتابعة المخصص
        "reply": str(data.get("reply") or "").strip()[:400],     # رد الرفض المهذب (خارج النطاق)
    }


def get_llm_decision(message, conversation=""):
    # الدالة الرئيسية
    #  conversation: نص المحادثة كاملة (أسئلة النظام + أجوبة المستخدم) ليقرر النموذج بناءً عليها
    global last_error
    if not config.LLM_API_KEY:
        last_error = "LLM_API_KEY is missing"
        logger.warning("LLM_API_KEY missing - falling back to local policy rules.")
        return None

    try:
        user_prompt = f"Conversation so far:\n{conversation}" if conversation else message
        raw_response = ask_llm(SYSTEM_PROMPT, user_prompt)
        parsed_data = parse_json(raw_response)
        validated_result = validate_llm_output(parsed_data)

        if validated_result is None:
            last_error = "the model answer was not valid JSON / not an allowed value"
            logger.warning("Invalid LLM payload - falling back to local policy rules. Raw: %s", str(raw_response)[:200])
        else:
            last_error = ""
        return validated_result

    except Exception as exc:
        last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
        logger.warning("LLM API call failed (%s) - falling back to local policy rules.", last_error)
        return None


def get_follow_up_question(conversation):
    """ النموذج يكتب سؤال المتابعة بنفسه"""
    if not config.LLM_API_KEY:
        return None
    try:
        text = ask_llm(QUESTION_PROMPT, conversation, json_mode=False) or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip().strip('"')
        return text[:300] or None
    except Exception as exc:
        logger.warning("LLM question failed (%s).", type(exc).__name__)
        return None


def get_troubleshooting_steps(message, category, device_or_system=""):
    """النموذج يقترح خطوات حل ذاتي للتذاكر العادية فقط. المخرجات تُفحص في response_drafter.clean_llm_steps."""
    if not config.LLM_API_KEY:
        return None
    try:
        prompt = (f"Category: {category}\nDevice/system: {device_or_system or 'not given'}\n"
                  f"Employee message: {message}")
        data = parse_json(ask_llm(STEPS_PROMPT, prompt))
        return data.get("steps") if data else None
    except Exception as exc:
        logger.warning("LLM steps failed (%s) - using curated steps.", type(exc).__name__)
        return None


def get_chat_reply(ticket, history, question):
    """ رد الشات بناءً على الـ context (facts + آخر الرسائل). يرجع None عند أي فشل"""
    if not config.LLM_API_KEY:
        return None

    try:
        from context_strategies import build_context
        client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, timeout=20)
        completion = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=build_context(ticket, history, question),
            temperature=config.LLM_TEMPERATURE,
        )
        reply = (completion.choices[0].message.content or "").strip()
        return reply[:1000] or None
    except Exception as exc:
        logger.warning("LLM chat reply failed (%s) - using a simple reply.", type(exc).__name__)
        return None
