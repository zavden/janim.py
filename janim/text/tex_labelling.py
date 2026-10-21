"""ManimGL string labelling as Janim implements it, over Unicode code points."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Labelling:
    body: str
    spans: tuple


def selectors(value):
    values = [value] if isinstance(value, str) else list(value)
    if any(not isinstance(item, str) for item in values):
        raise TypeError("isolate/t2c selectors must be strings")
    return values


def command_matches(text):
    pattern = re.compile(r"\\(?:[a-zA-Z]+|.)|{+|}+", flags=re.S)
    result = []
    opened = []
    for match in pattern.finditer(text):
        token = match.group()
        if token.startswith("{"):
            opened.append((match.span(), len(result)))
        elif token.startswith("}"):
            start, end = match.span()
            while True:
                if not opened:
                    raise ValueError("Missing '{' inserted: a closing brace has no opening brace")
                (first, last), index = opened.pop()
                count = min(last - first, end - start)
                result.insert(index, ((last - count, last), 1, count))
                result.append(((start, start + count), -1, count))
                start += count
                if start < end:
                    continue
                last -= count
                if first < last:
                    opened.append(((first, last), index))
                break
        else:
            result.append((match.span(), 0, 0))
    if opened:
        raise ValueError("Missing '}' inserted: an opening brace has no closing brace")
    return result


def spans_of(text, selector):
    if not selector:
        raise ValueError("isolate/t2c: an empty pattern selects nothing")
    return [match.span() for match in re.finditer(re.escape(selector), text)]


def color_command(label, flag):
    if flag < 0:
        return "}}"
    red_green, blue = divmod(label, 256)
    red, green = divmod(red_green, 256)
    return "{{\\color[RGB]{" + f"{red}, {green}, {blue}" + "}"


def label_tex(text, isolate=(), t2c=()):
    configured = [span for selector in selectors(t2c) for span in spans_of(text, selector)]
    isolated = [span for selector in selectors(isolate) for span in spans_of(text, selector)]
    commands = command_matches(text)
    categories = (configured, isolated, [], [command[0] for command in commands])

    def key(item):
        category, index, flag = item
        first, last = categories[category][index][::flag]
        return first, flag * (2 if first != last else -1), -last, flag * category, flag * index

    items = sorted(
        ((category, index, flag) for category, spans in enumerate(
            categories,
        ) for index in range(
            len(spans),
        ) for flag in (1, -1)),
        key=key,
    )
    inserted = []
    labelled = []
    overlapping = []
    mismatched = []
    label = 1
    protection = 0
    brackets = [0]
    bracket_count = 0
    opened_commands = []
    opened = []
    for category, index, flag in items:
        if category >= 2:
            protection += flag
            if flag == 1 or category == 2:
                continue
            inserted.append((index, 0))
            _, command_flag, _ = commands[index]
            if command_flag == 1:
                bracket_count += 1
                brackets.append(bracket_count)
                opened_commands.append((len(inserted), index))
                continue
            if command_flag == 0:
                continue
            position, opening = opened_commands.pop()
            brackets.pop()
            if commands[opening][2] < 2:
                continue
            labelled.append((commands[opening][0][1], commands[index][0][0]))
            inserted.insert(position, (label, 1))
            inserted.insert(-1, (label, -1))
            label += 1
            continue
        if flag == 1:
            opened.append((len(inserted), category, index, protection, brackets.copy()))
            continue
        span = categories[category][index]
        position, previous_category, previous_index, previous_protection, previous_brackets = opened.pop()
        if previous_category != category or previous_index != index:
            overlapping.append(span)
            continue
        if previous_protection or protection:
            continue
        if previous_brackets != brackets:
            mismatched.append(span)
            continue
        labelled.append(span)
        inserted.insert(position, (label, 1))
        inserted.append((label, -1))
        label += 1
    if overlapping:
        names = [text[first:last] for first, last in overlapping]
        raise ValueError(
            f"isolate/t2c: partly overlapping substrings {names}; patterns may nest but cannot cross",
        )
    if mismatched:
        names = [text[first:last] for first, last in mismatched]
        raise ValueError(f"isolate/t2c: {names} crosses a brace level")
    labelled.insert(0, (0, len(text)))
    inserted.insert(0, (0, 1))
    inserted.append((0, -1))
    pieces = []
    for index, flag in inserted:
        if flag == 0:
            span = commands[index][0]
            pieces.append((span, text[slice(*span)]))
        else:
            position = labelled[index][flag < 0]
            pieces.append(((position, position), color_command(index, flag)))
    output = []
    for index in range(len(pieces) - 1):
        output.append(text[pieces[index][0][1]:pieces[index + 1][0][0]])
        if index < len(pieces) - 2:
            output.append(pieces[index + 1][1])
    return Labelling("".join(output), tuple(labelled))
