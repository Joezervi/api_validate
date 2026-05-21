from app.parsers.zrevi_parse import ZerviParser


def get_parser(customer_name):

    parsers = {"zervi": ZerviParser()}

    return parsers.get(customer_name.lower())
