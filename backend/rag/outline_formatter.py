import re

MODULE_HEADING = re.compile(r"^\s*([1-6])(?:\.0\b|(?!\.)\s+)(?:\1\s+)?(.+?)\s+(\d{1,2})\s*$")
MODULE_START = re.compile(r"^\s*([1-6])(?:\.0\b|(?!\.)\s+)(?!\s*\d+\.\d+)(.*)$")
UNIT_HEADING = re.compile(r"^\s*(?:[1-6](?:\.0|\.)?\s+)?([1-6])\.(\d+)\b\s*(.*)$")
REFERENCE_HEADING = re.compile(
    r"^(Text\s*books?:|Reference\s*books?:|References?:|Online\s*References?:|Course\s*Assessment:|End\s*Semester\s*Examination:|Course\s*Objective[s]?:|Course\s*Outcome[s]?:|Lab\s*Objective[s]?:|Lab\s*Outcome[s]?:|Assessment\b|Term\s*Work\b)",
    re.IGNORECASE,
)
SELF_LEARNING_HEADING = re.compile(
    r"^Self[- ]learning Topics?:?\s*(.*)$",
    re.IGNORECASE,
)
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
NUMBER_TOKEN = r"(?:\d+(?:st|nd|rd|th)?|" + "|".join(NUMBER_WORDS) + r")"


def _number_value(value: str) -> int:
    normalized = value.casefold()
    if normalized in NUMBER_WORDS:
        return NUMBER_WORDS[normalized]
    return int(re.sub(r"(?:st|nd|rd|th)$", "", normalized))


def select_requested_modules(question: str, modules: list[dict]) -> list[dict]:
    available = sorted(modules, key=lambda module: module["number"])
    if not available:
        return []

    normalized_question = question.casefold()
    count_match = re.search(
        rf"\b(?:first|initial|top)\s+({NUMBER_TOKEN})(?:\s+modules?)?\b",
        normalized_question,
    )
    if count_match:
        count = _number_value(count_match.group(1))
        return available[:count]

    last_match = re.search(
        rf"\b(?:last|final)\s+({NUMBER_TOKEN})(?:\s+modules?)?\b",
        normalized_question,
    )
    if last_match:
        count = _number_value(last_match.group(1))
        return available[-count:]

    between_match = re.search(
        rf"\b(?:modules?\s+)?between\s+({NUMBER_TOKEN})\s+and\s+({NUMBER_TOKEN})(?:\s+modules?)?\b",
        normalized_question,
    )
    if between_match:
        start = _number_value(between_match.group(1))
        end = _number_value(between_match.group(2))
        low, high = sorted((start, end))
        return [module for module in available if low <= module["number"] <= high]

    range_match = re.search(
        rf"\b(?:modules?\s+(?:from\s+)?|from\s+(?:module\s+)?)?({NUMBER_TOKEN})\s*(?:-|\bto\b|\bthrough\b|\buntil\b)\s*({NUMBER_TOKEN})(?:\s+modules?)?\b",
        normalized_question,
    )
    if range_match:
        start = _number_value(range_match.group(1))
        end = _number_value(range_match.group(2))
        low, high = sorted((start, end))
        return [module for module in available if low <= module["number"] <= high]

    list_match = re.search(
        rf"\b(?:modules?\s+({NUMBER_TOKEN}(?:\s*(?:,|and|&)\s*{NUMBER_TOKEN})+)|({NUMBER_TOKEN}(?:\s*(?:,|and|&)\s*{NUMBER_TOKEN})+)\s+modules?)\b",
        normalized_question,
    )
    if list_match:
        requested = {
            _number_value(token)
            for token in re.findall(NUMBER_TOKEN, list_match.group(1) or list_match.group(2))
        }
        return [module for module in available if module["number"] in requested]

    single_match = re.search(
        rf"\bmodule\s+({NUMBER_TOKEN})\b|\b({NUMBER_TOKEN})\s+module\b",
        normalized_question,
    )
    if single_match:
        requested = _number_value(single_match.group(1) or single_match.group(2))
        return [module for module in available if module["number"] == requested]

    return available


def extract_module_outlines(pages: list[dict]) -> list[dict]:
    modules = {}
    current_module = None
    current_content = None
    skip_references = False
    pending_module = None

    def start_module(module_number: int, title: str, hours: int, page_number: int):
        nonlocal current_module, current_content, skip_references
        current_module = module_number
        modules[module_number] = {
            "title": title.strip(),
            "hours": hours,
            "pages": [page_number],
            "description": "",
            "units": [],
            "self_learning": [],
        }
        current_content = ("description",)
        skip_references = False

    for page in pages:
        page_number = page["page_number"]
        for source_line in page.get("text", "").splitlines():
            line = " ".join(source_line.split())
            if not line or line == str(page_number):
                continue
            if line.isdigit():
                if pending_module and len(line) <= 2:
                    pass
                else:
                    continue
            if line.startswith(
                (
                    "SIES Graduate School",
                    "Department of Computer Engineering",
                    "Department of Computer",
                    "Bachelor of Engineering",
                    "Bachelor of Technology",
                )
            ):
                continue
            if line.casefold() in {
                "module",
                "no.",
                "unit",
                "topics",
                "topics hrs.",
                "no. topics",
                "mapped",
                "learning",
                "outcome",
                "outcome (lo)",
                "learning outcome (lo)",
                "mapped learning outcome (lo)",
            }:
                continue

            module_match = MODULE_HEADING.match(line)
            if module_match:
                start_module(
                    int(module_match.group(1)),
                    module_match.group(2),
                    int(module_match.group(3)),
                    page_number,
                )
                continue

            module_start = MODULE_START.match(line)
            is_dot_zero = bool(re.match(r"^\s*[1-6]\.0\b", line))
            if module_start and (not skip_references or is_dot_zero):
                module_number = int(module_start.group(1))
                heading_text = module_start.group(2).strip()
                hours_match = re.match(r"^(.*?)\s+(\d{1,2})$", heading_text)
                if hours_match:
                    start_module(
                        module_number,
                        hours_match.group(1),
                        int(hours_match.group(2)),
                        page_number,
                    )
                else:
                    pending_module = (module_number, heading_text, page_number)
                continue

            unit_match = UNIT_HEADING.match(line)

            if pending_module:
                module_number, heading_text, start_page = pending_module
                combined_heading = " ".join((heading_text, line)).strip()
                hours_match = re.match(r"^(.*?)\s+(\d{1,2})$", combined_heading)
                if hours_match:
                    start_module(
                        module_number,
                        hours_match.group(1),
                        int(hours_match.group(2)),
                        start_page,
                    )
                    pending_module = None
                    continue
                elif unit_match:
                    start_module(
                        module_number,
                        heading_text,
                        0,
                        start_page,
                    )
                    pending_module = None
                else:
                    if len(combined_heading) > 120 or REFERENCE_HEADING.match(line):
                        pending_module = None
                    else:
                        pending_module = (module_number, combined_heading, start_page)
                    continue

            if REFERENCE_HEADING.match(line):
                if current_module is not None:
                    skip_references = True
                    current_content = None
                continue

            if skip_references:
                if (
                    unit_match
                    and current_module is not None
                    and int(unit_match.group(1)) == current_module
                ):
                    skip_references = False
                else:
                    continue

            if current_module is None:
                continue

            module = modules[current_module]

            if re.match(r"(?i)^total\s+\d+\b", line):
                current_module = None
                current_content = None
                continue

            line = re.sub(r"\b(?:CO|LO)\d+(?:\s*,\s*(?:CO|LO)\d+)*\b", "", line).strip()
            if not line:
                continue

            if page_number not in module["pages"]:
                module["pages"].append(page_number)

            unit_match = UNIT_HEADING.match(line)
            if unit_match and int(unit_match.group(1)) == current_module:
                module["units"].append(
                    {
                        "number": f"{unit_match.group(1)}.{unit_match.group(2)}",
                        "text": re.sub(r"\b(?:CO|LO)\d+(?:\s*,\s*(?:CO|LO)\d+)*\b", "", unit_match.group(3)).strip(),
                    }
                )
                current_content = ("units", len(module["units"]) - 1)
                continue

            self_learning_match = SELF_LEARNING_HEADING.match(line)
            if self_learning_match:
                module["self_learning"].append(self_learning_match.group(1).strip())
                current_content = ("self_learning", len(module["self_learning"]) - 1)
                continue

            if current_content:
                if len(current_content) == 1:
                    module[current_content[0]] = " ".join(
                        part for part in (module[current_content[0]], line) if part
                    )
                else:
                    content = module[current_content[0]][current_content[1]]
                    if isinstance(content, dict):
                        content["text"] = " ".join(
                            part for part in (content["text"], line) if part
                        )
                    else:
                        module[current_content[0]][current_content[1]] = " ".join(
                            part for part in (content, line) if part
                        )

    outlines = []
    for module_number, module in sorted(modules.items()):
        if module["hours"]:
            lines = [
                f"## Module {module_number}: {module['title']} ({module['hours']} hours)"
            ]
        else:
            lines = [
                f"## Module {module_number}: {module['title']}"
            ]
        if module["description"]:
            lines.append(module["description"])
        lines.extend(
            f"**Unit {unit['number']}**\n{unit['text']}" for unit in module["units"]
        )
        if module["self_learning"]:
            lines.append(
                "**Self-learning Topics:**\n"
                + " ".join(topic for topic in module["self_learning"] if topic)
            )
        mod_text = "\n\n".join(lines)
        if "**Self-learning Topics:**" not in mod_text:
            mod_text = re.sub(
                r'(?i)\s*(?:\.|\b)\s*Self-?Learning(?:\s*topics?)?\s*:\s*',
                r'.\n\n**Self-learning Topics:**\n',
                mod_text,
            )
        outlines.append(
            {
                "number": module_number,
                "text": mod_text,
                "pages": module["pages"],
            }
        )
    return outlines
