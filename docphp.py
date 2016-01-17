import sublime
import sublime_plugin
import xml.etree.ElementTree as ET
import re
import os
import subprocess
import glob
import shutil
import urllib.request
import io
import tarfile
import webbrowser
import time

from urllib.request import urlopen


docphp_languages = {}
entities = {}
currentView = False
currentSettings = None
openfiles = {}
isoEntities = {}

language = ''

downloading = False

# for auto show
prevTime = 0
delaying = False


def plugin_loaded():
    global currentSettings, language
    currentSettings = sublime.load_settings('docphp.sublime-settings')
    language = currentSettings.get('language')
    if not language:
        docphpPath = getDocphpPath()
        if not os.path.isdir(docphpPath + 'language'):
            os.makedirs(docphpPath + 'language')
        installLanguagePopup(languageName='en', use_svn=False, set_fallback=True)
    else:
        tarGzPath = getTarGzPath()
        tar = tarfile.open(tarGzPath)
        openfiles[tarGzPath] = tar
        sublime.set_timeout_async(tar.getmembers, 0)


def plugin_unloaded():
    try:
        for k in openfiles:
            openfiles[k].close()
    except Exception as e:
        if getSetting('debug'):
            print(e)
    sublime.save_settings('docphp.sublime-settings')


def getSetting(key):
    global currentView, currentSettings

    local = 'docphp.' + key
    if currentView:
        settings = currentView.settings()
        if settings:
            return settings.get(local, currentSettings.get(key))

    return currentSettings.get(key)


def setSetting(key, value):
    global currentView, currentSettings

    local = 'docphp.' + key
    if currentView:
        settings = currentView.settings()
        if settings:
            settings.set(local, value)

    currentSettings.set(key, value)
    sublime.save_settings('docphp.sublime-settings')


def isSvn():
    languages = getSetting('languages')
    try:
        setting = languages[language]
        return setting == 'svn'
    except Exception:
        return


def getLanguageList(languageName=None):
    languages = sublime.decode_value(sublime.load_resource('Packages/docphp/languages.json'))
    languages = [(k, languages[k]) for k in sorted(languages.keys())]

    languageNameList = []
    languageList = []
    for k, v in languages:
        if k == languageName:
            index = len(languageList)
        languageNameList.append(k)
        languageList.append(k + ' ' + v['name'] + ' (' + v['nativeName'] + ')')

    return languageNameList, languageList


def generateEntities():
    global entities

    def generate():
        entitiesLocal = {}
        for entitiesFile in glob.glob(getI18nSvnPath() + '*.ent'):
            with open(entitiesFile, 'r', -1, 'utf8') as f:
                entitiesText = f.read(10485760)
            matches = re.findall("^<!ENTITY\s+([a-zA-Z0-9._-]+)\s+(['\"])([\s\S]*?)\\2>$", entitiesText, re.MULTILINE)
            for match in matches:
                key, quote, content = match
                entitiesLocal[key] = re.sub(' xmlns="[^"]+"', '', content)
        return entitiesLocal

    entities[language] = getJsonOrGenerate('entities', generate)


def decodeEntity(xml):
    if language not in entities:
        generateEntities()

    def parseEntity(match):
        entity = match.group(1)
        if entity not in entities[language]:
            return " <b>" + entity.upper() + "</b> "
        else:
            return entities[language][entity]

    i = 10
    while i:
        i -= 1
        newxml = re.sub('&([a-zA-Z0-9._-]+);', parseEntity, xml)
        if newxml == xml:
            break
        else:
            xml = newxml
    return xml


def decodeIsoEntity(xml):
    global isoEntities
    if not isinstance(xml, str):
        print(xml)
        return xml
    if isoEntities:
        forward, reverse = isoEntities
    else:
        forward = sublime.decode_value(sublime.load_resource('Packages/docphp/IsoEntities.json'))
        reverse = dict((v, k) for k, v in forward.items())
        isoEntities = (forward, reverse)

    def parseEntity(match):
        entity = match.group(1)
        try:
            if entity.isdigit():
                return reverse[int(entity)]
            else:
                return chr(forward[entity])
        except:
            return match.group(0)
    xml = re.sub('&([a-zA-Z0-9]+);', parseEntity, xml)
    return xml


def getDocphpPath():
    return sublime.cache_path() + '/docphp/'


def getTarGzPath():
    return sublime.cache_path() + '/docphp/language/php_manual_' + language + '.tar.gz'


def getI18nCachePath():
    return sublime.cache_path() + '/docphp/language/' + language + '/'


def getI18nSvnPath():
    return sublime.cache_path() + '/docphp/language/' + language + '/phpdoc/'


def loadLanguage():
    global docphp_languages

    if not isSvn():
        if not os.path.isfile(getTarGzPath()):
            return False

        tarGzPath = getTarGzPath()
        try:
            tar = openfiles[tarGzPath]
        except KeyError:
            tar = tarfile.open(tarGzPath)
            openfiles[tarGzPath] = tar
        tar.getmembers()

        def generate():
            symbols = {}

            for tarinfo in tar:
                m = re.search('^php-chunked-xhtml/(.*)\.html$', tarinfo.name)
                if m:
                    symbols[m.group(1)] = m.group(0)
            return symbols

        symbols = getJsonOrGenerate('packed_symbols', generate)
        docphp_languages[language] = {"symbolList": symbols, "definition": {}}

        return True

    if not os.path.isdir(getI18nSvnPath()):
        return False

    def generate():
        symbols = {}
        i18nPath = getI18nSvnPath()
        pathLen = len(i18nPath)
        for root, dirnames, filenames in os.walk(i18nPath):
            for xmlFile in filenames:
                for name in re.findall('^(.+)\.xml$', xmlFile):
                    symbols[name] = os.path.join(root[pathLen:], xmlFile)
        return symbols

    symbols = getJsonOrGenerate('packed_symbols', generate)
    docphp_languages[language] = {"symbolList": symbols, "definition": {}}
    return True


def getJsonOrGenerate(name, callback):
    filename = getI18nCachePath() + name + '.json'
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf8') as f:
            json = f.read(10485760)
        content = sublime.decode_value(json)

    else:
        content = callback()

        dirname = os.path.dirname(filename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        with open(filename, 'w', encoding="utf8") as f:
            f.write(sublime.encode_value(content))

    return content


def getSymbolDescription(symbol, use_language=False, fallback=False):
    if use_language:
        language = use_language
    else:
        global language

    if language not in docphp_languages and not loadLanguage():
        sublime.error_message('The language "' + language + '" not installed\nYou can use\n\n   docphp: checkout language\n\nto checkout a language pack')
        return None, False

    symbol = symbol.lower()
    symbolList = docphp_languages[language]["symbolList"]
    if not isSvn():
        if not fallback:
            for prefix in ['function.', 'book.', 'class.']:
                if prefix + symbol in symbolList:
                    symbol = prefix + symbol
                    break

    if symbol not in symbolList:
        if not fallback and getSetting('language_fallback'):
            return getSymbolDescription(symbol, getSetting('language_fallback'), True)
        else:
            return None, None
    else:

        if symbol not in docphp_languages[language]["definition"]:
            if isSvn():
                output = getSymbolFromXml(symbol)
            else:
                output = getSymbolFromHtml(symbol)

            output = decodeIsoEntity(output)
            docphp_languages[language]["definition"][symbol] = output
        return symbol, docphp_languages[language]["definition"][symbol]


def getSymbolFromHtml(symbol):

    tarPath = getTarGzPath()
    try:
        tar = openfiles[tarPath]
    except KeyError:
        tar = tarfile.open(getTarGzPath())
        openfiles[tarPath] = tar
    member = tar.getmember(docphp_languages[language]["symbolList"][symbol])
    f = tar.extractfile(member)
    output = f.read().decode(errors='ignore')

    output = re.sub('[\s\S]+?(<div[^<>]+?id="'+re.escape(symbol)+'"[\s\S]+?)<div[^<>]+?class="manualnavbar[\s\S]+', '\\1', output)
    dic = {
        '&mdash;': '--',
        '&quot;': "'",
        '<br>': '',
        '&#039;': "'",
        '&$': "&amp;",
        '&raquo;': '>>',
    }
    pattern = "|".join(map(re.escape, dic.keys()))

    output = re.sub(pattern, lambda m: dic[m.group()], output)
    output = re.sub('(<h[1-6][^<>]*>)([^<>]*)(</h[1-6][^<>]*>)', '\\1<a href="http://php.net/manual/' +
                    language+'/'+symbol+'.php">\\2</a><br>\\3<a href="history.back">back</a>', output, count=1)

    output = '<style>#container{margin:10px}</style><div id="container">' + output + "</div>"
    return output


def getSymbolFromXml(symbol):

    defFile = docphp_languages[language]["symbolList"][symbol]

    with open(getI18nSvnPath() + defFile, 'r', encoding='utf8') as f:
        xml = f.read(10485760)
    xml = re.sub(' xmlns="[^"]+"', '', xml, 1)
    xml = decodeEntity(xml)
    xml = re.sub(' xlink:href="[^"]+"', '', xml)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        if getSetting('debug'):
            print(xml)
            raise e
        sublime.error_message('Cannot read definition of ' + symbol + ', please report this issue on github')
        return None, False
    output = ''

    refsect1 = root.find('refsect1[@role="description"]')
    if not refsect1:
        refsect1 = root.find('refsect1')

    methodsynopsis = refsect1.find('methodsynopsis')

    if not methodsynopsis:
        methodsynopsis = root.find('refsect1/methodsynopsis')

    output += '<type>' + methodsynopsis.find('type').text + '</type> <b style="color:#369">' + symbol + "</b> ("
    hasPrviousParam = False
    for methodparam in methodsynopsis.findall('methodparam'):

        output += ' '
        attrib = methodparam.attrib
        opt = False
        if "choice" in attrib and attrib['choice'] == 'opt':
            opt = True
            output += "["
        if hasPrviousParam:
            output += ", "
        output += '<type>' + methodparam.find('type').text + "</type> $" + methodparam.find('parameter').text
        if opt:
            output += "]"
        hasPrviousParam = True
    output += " )\n"

    # output += root.find('refnamediv/refpurpose').text.strip() + "\n\n";

    for para in refsect1.findall('para'):
        output += "   " + \
            re.sub("<.*?>", "", re.sub("<row>([\s\S]*?)</row>", "\\1<br>", re.sub("\s\s+", " ", ET.tostring(para, 'utf8', 'html').decode()))) + "\n"

    output += "\n"

    variablelist = root.findall('refsect1[@role="parameters"]/para/variablelist/varlistentry')
    for variable in variablelist:
        output += ET.tostring(variable.find('term/parameter'), 'utf8', 'html').decode() + " :\n"
        for para in variable.findall('listitem/para'):
            # TODO: parse table
            output += "   " + re.sub("<row>([\s\S]*?)</row>", "\\1<br>", re.sub("\s\s+", " ", ET.tostring(para, 'utf8', 'html').decode())) + "\n"
        output += "\n"
    output += "\n"

    returnvalues = root.findall('refsect1[@role="returnvalues"]/para')
    for para in returnvalues:
        output += re.sub("\s\s+", " ", ET.tostring(para, 'utf8', 'html').decode()).strip() + "\n"
    return output


class DocphpShowDefinitionCommand(sublime_plugin.TextCommand):
    history = []
    currentSymbol = ''

    def run(self, edit):
        global language, currentView
        view = self.view
        currentView = view

        window = view.window()
        language = getSetting('language')

        selection = view.sel()
        if not re.search('source\.php', view.scope_name(selection[0].a)):
            return

        region = view.word(selection[0])

        symbol = view.substr(region).replace('_', '-')

        # symbol = 'basename'

        symbol, symbolDescription = getSymbolDescription(symbol)
        if symbolDescription == None:
            if getSetting('prompt_when_not_found'):
                view.show_popup('not found', sublime.COOPERATE_WITH_AUTO_COMPLETE)
            return
        if symbolDescription == False:
            return

        if getSetting('use_panel') == False:
            output = symbolDescription
            if isSvn():
                output = re.sub('\n', '<br>\n', symbolDescription)
                output = re.sub('<parameter>', '<parameter style="color:#369;font-weight:900"><b>', output)
                output = re.sub('</parameter>', '</b></parameter>', output)
                output = re.sub('<type>', '<type style="color:#369">', output)
            if getSetting('debug'):
                print(output)

            self.currentSymbol = symbol

            def on_hide():
                self.currentSymbol = ''
                self.history = []

            def on_navigate(url):
                if url[:4] == 'http':
                    webbrowser.open_new(url)
                    return True

                if url == 'history.back':
                    symbol = self.history.pop()
                    self.currentSymbol = symbol

                else:
                    self.history.append(self.currentSymbol)
                    symbol = url[:url.find('.html')]
                    self.currentSymbol = symbol

                # It seems sublime will core when the output is too long
                # In some cases the value can set to 76200, but we use a 65535 for safety.
                symbol, content = getSymbolDescription(symbol)[:65535]
                view.update_popup(content)
            width, height = view.viewport_extent()

            view.show_popup(output, flags=sublime.COOPERATE_WITH_AUTO_COMPLETE | sublime.HTML, location=-1, max_width=min(getSetting('popup_max_width'), width),
                            max_height=min(getSetting('popup_max_height'), height), on_navigate=on_navigate,
                            on_hide=on_hide)

            return
        else:
            output = re.sub('<.*?>', '', symbolDescription)
            name = 'docphp'

            panel = window.get_output_panel(name)
            window.run_command("show_panel", {"panel": "output."+name})
            panel.set_read_only(False)
            panel.insert(edit, panel.size(), output + '\n')
            panel.set_read_only(True)


def installLanguagePopup(languageName=None, use_svn=False, set_fallback=False):
    global downloading
    if downloading:
        sublime.message_dialog('Another progress is working for checkout ' + downloading + '. Please try again later.')
        return
    languageNameList, languageList = getLanguageList(languageName)

    def updateLanguage(index=None):
        if index == -1:
            return
        languageName = languageNameList[index]
        languagePath = getDocphpPath() + 'language/' + languageName

        def checkoutLanguage():
            if use_svn:
                sublime.status_message('checking out ' + languageName)
                global downloading
                downloading = languageName
                p = runCmd('svn', ['checkout', 'http://svn.php.net/repository/phpdoc/' + languageName + '/trunk', 'phpdoc_svn'], languagePath)
                out, err = p.communicate()
                downloading = False
                if p.returncode == 0:
                    if os.path.isdir(languagePath + '/phpdoc'):
                        shutil.rmtree(languagePath + '/phpdoc')

                    os.rename(languagePath + '/phpdoc_svn', languagePath + '/phpdoc')

                else:
                    if getSetting('debug'):
                        print(out)
                        print(err)
                    shutil.rmtree(languagePath + '/phpdoc_svn')
                    return False
            else:

                if not downloadLanguageGZ(languageName):
                    if getSetting('debug'):
                        print('download error')
                    return False

            setSetting('language', languageName)
            languageSettings = currentSettings.get('languages')

            if use_svn:
                languageSettings[languageName] = 'svn'
            else:
                languageSettings[languageName] = 'gz'

            setSetting('languages', languageSettings)
            if set_fallback:
                setSetting('language_fallback', languageName)

            loadLanguage()

            sublime.message_dialog('Language ' + languageName + ' is checked out')

        sublime.set_timeout_async(checkoutLanguage, 0)
    if languageName:
        updateLanguage(index)
    else:
        currentView.window().show_quick_panel(languageList, updateLanguage)


def downloadLanguageGZ(name):
    err = None
    try:
        url = 'http://php.net/distributions/manual/php_manual_' + name + '.tar.gz'

        filename = getDocphpPath() + 'language/php_manual_' + name + '.tar.gz'

        response = urlopen(url)
        try:
            totalsize = int(response.headers['Content-Length'])  # assume correct header
        except NameError:
            totalsize = None
        except KeyError:
            totalsize = None

        outputfile = open(filename, 'wb')

        readsofar = 0
        chunksize = 8192
        try:
            global downloading
            downloading = name
            while(True):
                # download chunk
                data = response.read(chunksize)
                if not data:  # finished downloading
                    break
                readsofar += len(data)
                outputfile.write(data)  # save to filename
                if totalsize:
                    # report progress
                    percent = readsofar * 1e2 / totalsize  # assume totalsize > 0
                    sublime.status_message('%.0f%% checking out %s' % (percent, name,))
                else:
                    kb = readsofar / 1024
                    sublime.status_message('%.0f KB checking out %s' % (kb, name,))
        finally:
            outputfile.close()
            downloading = False
        if readsofar != totalsize:
            return False
        else:
            return True

        def reporthook(blocknum, blocksize, totalsize):
            readsofar = blocknum * blocksize
            if totalsize > 0:
                percent = readsofar * 1e2 / totalsize
                s = "\r%5.1f%% %*d / %d" % (percent, len(str(totalsize)), readsofar, totalsize)
                status_message(s)
            else:  # total size is unknown
                status_message("read %d\n" % (readsofar,))

        urlretrieve(url, filename, reporthook)

        return True

    except (urllib.error.HTTPError) as e:
        err = '%s: HTTP error %s contacting API' % (__name__, str(e.code))
        if e.code == 404:
            # fall back to SVN
            installLanguagePopup(name, use_svn=True)
            return False

    except (urllib.error.URLError) as e:
        err = '%s: URL error %s contacting API' % (__name__, str(e.reason))
    except Exception as e:
        err = e.__class__.__name__
        print(e.args)

    sublime.message_dialog('Language ' + name + ' checkout failed. Please try again.')

    if getSetting('debug'):
        print(err)
    return


def runCmd(binType, params, cwd=None):
    binary = getSetting(binType + '_bin')
    params.insert(0, binary)
    if not os.path.isfile(binary) and binary != binType:
        sublime.error_message("Can't find " + binary + " binary file at " + binary)
        return False

    try:
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, shell=False, startupinfo=startupinfo)
        else:
            p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, shell=False)
        return p

    except FileNotFoundError:
        message = 'Cannot run ' + binType + ' command, please check your settings.'
        if binType == 'svn':
            message += '\n\nSVN is needed by DocPHP for checking out this language pack.'
        sublime.error_message(message)
        return False


class DocphpCheckoutLanguageCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        view = self.view
        global currentView
        currentView = view

        installLanguagePopup()


class DocphpSelectLanguageCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        global currentView
        view = self.view
        currentView = view

        languageNameListAll, languageListAll = getLanguageList()
        availableLanguages = getSetting('languages')
        languageNameList = []
        languageList = []

        for k in availableLanguages:
            index = languageNameListAll.index(k)
            languageNameList.append(languageNameListAll[index])
            languageList.append(languageListAll[index])

        def selectLanguageCallback(index):
            global language
            if index != -1:
                language = languageNameList[index]
                setSetting('language', language)
                sublime.set_timeout_async(loadLanguage, 0)

        currentView.window().show_quick_panel(languageList, selectLanguageCallback)


def doAutoShow():
    global delaying
    delayTime = getSetting('auto_delay')
    if (time.time() - prevTime) * 1000 > delayTime:
        delaying = False
        if not currentView.is_popup_visible():
            currentView.run_command('docphp_show_definition')
    else:
        sublime.set_timeout_async(doAutoShow, int(delayTime - (time.time() - prevTime) * 1000) + 50)


class DocPHPListener(sublime_plugin.EventListener):

    def on_activated(self, view):
        global currentView
        currentView = view

    def on_selection_modified_async(self, view):
        global prevTime, delaying

        if not getSetting('auto'):
            return
        prevTime = time.time()
        if not delaying:
            sublime.set_timeout_async(doAutoShow, getSetting('auto_delay') + 50)
            delaying = True
