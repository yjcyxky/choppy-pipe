# parsePythonValue.py
#
# Copyright, 2006, by Paul McGuire
#

from pyparsing import (Suppress, Regex, Forward, unicodeString,
                       quotedString, oneOf, Literal, replaceWith,
                       Group, Optional, delimitedList)


def cvtBool(t):
    return t[0] == 'True'


def cvtInt(toks):
    return int(toks[0])


def cvtReal(toks):
    return float(toks[0])


def cvtTuple(toks):
    return tuple(toks.asList())


def cvtDict(toks):
    return dict(toks.asList())


# define punctuation as suppressed literals
lparen, rparen, lbrack, rbrack, lbrace, rbrace, colon = map(Suppress, "()[]{}:")
identifier = Regex(r"[a-zA-Z_][\w]+")
integer = Regex(r"[+-]?\d+").setName("integer").setParseAction(cvtInt)
real = Regex(r"[+-]?\d+\.\d*([Ee][+-]?\d+)?").setName("real").setParseAction(cvtReal)
tupleStr = Forward()
listStr = Forward()
dictStr = Forward()

unicodeString.setParseAction(lambda t: t[0][2:-1].decode('unicode-escape'))
quotedString.setParseAction(lambda t: t[0][1:-1])
boolLiteral = oneOf("True False").setParseAction(cvtBool)
noneLiteral = Literal("None").setParseAction(replaceWith(None))

listItem = real | integer | quotedString | unicodeString | boolLiteral | noneLiteral | Group(listStr) | tupleStr | dictStr

tupleStr << (Suppress("(") + Optional(delimitedList(listItem)) + Optional(Suppress(",")) + Suppress(")"))
tupleStr.setParseAction(cvtTuple)

listStr << (lbrack + Optional(delimitedList(listItem) + Optional(Suppress(","))) + rbrack)

dictEntry = Group(listItem + colon + listItem)
dictStr << (lbrace + Optional(delimitedList(dictEntry) + Optional(Suppress(","))) + rbrace)
dictStr.setParseAction(cvtDict)

lparen = Suppress('(')
rparen = Suppress(')')
quote = Suppress('"')
eq = Suppress('=')

plugin_kwarg = (lparen + delimitedList(Group(identifier + Optional(eq + listItem))))


def test():
    test_str = '(arg1=1, arg2="haha", arg3=True)'
    items = plugin_kwarg.parseString(test_str).asList()
    kwargs = {i[0]: i[1] for i in items if len(i) == 2}
    print(kwargs)
