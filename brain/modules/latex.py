class LatexTable:

    def __init__(self):
        self.table = ""

    def __str__(self):
        return self.table

    def begin_tabular(self, cols):
        self.table += f"\\begin{{tabular}}{{{cols}}}\n"

    def end_tabular(self):
        self.table += "\\end{tabular}\n"

    def add_line(self, line):
        self.table += f"{line} \n"

    def add_row(self, row):
        self.table += f"{' & '.join([str(r) for r in row])} \\\\\n"

    def add_hline(self):
        self.table += "\\hline\n"

    def add_toprule(self):
        self.table += "\\toprule\n"

    def add_midrule(self):
        self.table += "\\midrule\n"

    def add_bottomrule(self):
        self.table += "\\bottomrule\n"


class LatexGlossaries:

    @staticmethod
    def apigls(name):
        if name == "APPLE":
            return "\\glsentryshort{apple}"
        elif name == "BAIDU":
            return "\\glsentryshort{baidu}"
        elif name == "FACEBOOK":
            return "\\glsentryshort{facebook}"
        elif name == "GITHUB":
            return "\\glsentryshort{github}"
        elif name == "GOOGLE":
            return "\\glsentryshort{google}"
        elif name == "LINKEDIN":
            return "\\glsentryshort{linkedin}"
        elif name == "MICROSOFT":
            return "\\glsentryshort{microsoft}"
        elif name == "QQ":
            return "\\glsentryshort{qq}"
        elif name == "SINA_WEIBO":
            return "\\glsentryshort{sinaweibo}"
        elif name == "TWITTER_1.0":
            return "\\glsentryshort{twitter1}"
        elif name == "WECHAT":
            return "\\glsentryshort{wechat}"

    @staticmethod
    def sdkgls(name):
        if name == "SIGN_IN_WITH_APPLE":
            return "\\glsentryshort{siwa}"
        elif name == "GOOGLE_ONE_TAP":
            return "\\glsentryshort{got}"
        elif name == "GOOGLE_SIGN_IN_DEPRECATED":
            return "\\glsentryshort{gsi}"
        elif name == "SIGN_IN_WITH_GOOGLE":
            return "\\glsentryshort{siwg}"
        elif name == "FACEBOOK_LOGIN":
            return "\\glsentryshort{fl}"
