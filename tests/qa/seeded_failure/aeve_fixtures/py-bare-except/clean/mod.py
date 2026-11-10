def read_value(parser, text):
    try:
        return parser(text)
    except ValueError:
        return None
