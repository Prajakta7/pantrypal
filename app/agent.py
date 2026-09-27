"""The chat agent: Gemini with function calling over the ToolBox."""
from google.genai import types

from app.tools import TOOL

MAX_TOOL_ROUNDS = 5

SYSTEM = """You are PantryPal, a friendly kitchen assistant who helps people cook with what they have,
waste less food and stay safe. Today is {weekday}, {today} in the user's time zone.
The pantry has {n_items} items; {n_soon} expire within 3 days or already have.
Saved diet: {diet}. Ingredients they avoid: {avoid}.

Rules:
- Always use tools for pantry contents, recipes and recalls. Never invent items, recipes or recalls.
- When the user lists groceries, call add_pantry_items once with all of them. If they don't give an
  expiry, estimate a typical shelf life and briefly say you estimated it.
- When suggesting recipes, prefer ones that use food expiring soon, and mention what's missing.
- Recalls: for name-only matches, tell the user to compare the brand and lot codes on their package.
  If a product matches, advise not to eat it and to follow the FDA notice. Never say a food is
  definitely safe; say no matching recalls were found.
- Every recipe suggestion follows the saved diet automatically. If the user states a diet ("I'm
  vegetarian", "we eat eggs but no meat", "we eat chicken", "no mushrooms"), save it with set_diet.
  Vegetarian means no meat, fish or eggs; eggetarian allows eggs; non-veg means chicken and eggs, but
  no other meat or fish. Never suggest a recipe that breaks the saved diet without saying so.
- Understand Indian and Hindi food names (haldi, jeera, dhania, hing, dahi, atta, rava, toor dal, palak,
  bhindi). Keep the user's own name when adding items. Put spices and masalas in 'Spices & masalas'
  and dals in 'Dals & lentils'. Spices are tracked like any other item, so say when one is missing.
- Diet labels come from AI or a person and can be wrong. Most hing is mixed with wheat flour, and some
  cheeses use animal rennet. For allergies, remind users to check labels.
- Keep replies short (1-3 sentences or a short list). Be warm and practical.
{demo_note}"""

DEMO_NOTE = "- The pantry currently holds DEMO items. If asked, say so and mention the 'Clear' button."


def system_prompt(toolbox, has_demo: bool) -> str:
    from app.kitchen import DIET_NAMES, freshness
    items = toolbox.items()
    soon = sum(1 for i in items if freshness(i, toolbox.today) in ("soon", "expired"))
    p = toolbox.prefs()
    return SYSTEM.format(weekday=toolbox.today.strftime("%A"), today=toolbox.today.isoformat(),
                         n_items=len(items), n_soon=soon,
                         diet=", ".join(DIET_NAMES[d] for d in p["diets"]) or "none saved",
                         avoid=", ".join(p["avoid"]) or "none",
                         demo_note=DEMO_NOTE if has_demo else "")


def to_contents(messages: list[dict]) -> list[types.Content]:
    return [types.Content(role="model" if m["role"] == "assistant" else "user",
                          parts=[types.Part.from_text(text=m["text"])]) for m in messages]


def run_chat(client, model: str, messages: list[dict], toolbox, has_demo: bool = False) -> dict:
    contents = to_contents(messages)
    system = system_prompt(toolbox, has_demo)
    config = types.GenerateContentConfig(
        system_instruction=system, tools=[TOOL], temperature=0.4,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    reply = ""
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.models.generate_content(model=model, contents=contents, config=config)
        calls = response.function_calls or []
        if not calls:
            reply = (response.text or "").strip()
            break
        contents.append(response.candidates[0].content)
        contents.append(types.Content(role="tool", parts=[
            types.Part.from_function_response(name=c.name, response=toolbox.call(c.name, dict(c.args or {})))
            for c in calls]))
    else:
        final = types.GenerateContentConfig(system_instruction=system, temperature=0.4)
        reply = (client.models.generate_content(model=model, contents=contents, config=final).text or "").strip()
    if not reply:
        reply = "Sorry, I couldn't put an answer together. Could you say that another way?"
    return {"reply": reply, "tool_calls": toolbox.calls, "cards": toolbox.cards}
