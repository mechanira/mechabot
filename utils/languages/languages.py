import os

class Languages:

    def __init__(self):

        self.translations = {}
        self.default_lang = "en"

        for file in os.listdir('sql'):
            if file.endswith('.txt'):

                lang = file.split(".")[0]
                self.translations[lang] = []

                for line in file:
                    self.translations[lang].append(line)

        return None

    def getText(ind, *args, *, lang = None):

        if not lang:
            lang = self.default_lang

        if ind > len(self.translations[lang]) or self.translations[lang][ind] == "":
            line = self.translations["en"][ind]
        else:
            line = self.translations[lang][ind]

        result = ""
        arg_ind = 0
        for i in range(0, len(line) - 1):
            if line[i] == '\\' and line[i + 1] == '?':
                if arg_ind < len(args):
                    result += args[arg_ind]
                arg_ind += 1
                i += 2
            else:
                result += line[i]

        return result
