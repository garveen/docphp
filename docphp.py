import sublime
import sublime_plugin
import re
import os
import shutil
import tarfile
import webbrowser
import time

from urllib.request import urlopen

package_name = 'DocPHPManualer'
setting_file = package_name + '.sublime-settings'

docphp_languages = {}
currentView = False
currentSettings = None
openfiles = {}
entities = {
    "iso": False,
    "html": False
}

language = ''

downloading = False

# for auto show
prevTime = 0
delaying = False


def plugin_loaded():
    global currentSettings, language, currentView
    currentSettings = sublime.load_settings(setting_file)
    language = currentSettings.get('language')
    currentView = sublime.active_window().active_view()

    docphpPath = getDocphpPath()
    if not os.path.isdir(docphpPath + 'language'):
        os.makedirs(docphpPath + 'language')

    from package_control import events

    if events.install(package_name):

        installLanguagePopup(is_init=True, set_fallback=True)
    else:
        tarGzPath = getTarGzPath()
        if os.path.isfile(tarGzPath):
            tar = tarfile.open(tarGzPath)
            openfiles[tarGzPath] = tar
            sublime.set_timeout_async(tar.getmembers, 0)


def plugin_unloaded():
    for k in openfiles:
        try:
            openfiles[k].close()
        except Exception as e:
            if getSetting('debug'):
                print(e)
    sublime.save_settings(setting_file)

    from package_control import events

    if events.remove(package_name):
        if os.path.isdir(getDocphpPath()):
            shutil.rmtree(getDocphpPath())


def getSetting(key):
    return currentSettings.get(key)


def setSetting(key, value):
    currentSettings.set(key, value)
    sublime.save_settings(setting_file)


def getLanguageList(languageName=None):
    languages = sublime.decode_value(sublime.load_resource('Packages/' + package_name + '/languages.json'))
    languages = [(k, languages[k]) for k in sorted(languages.keys())]

    languageNameList = []
    languageList = []
    index = None
    for k, v in languages:
        if k == languageName:
            index = len(languageList)
        languageNameList.append(k)
        languageList.append(k + ' ' + v['name'] + ' (' + v['nativeName'] + ')')

    return languageNameList, languageList, index


def decodeEntity(xml, category='iso'):
    global entities
    if not isinstance(xml, str):
        return xml
    if entities[category]:
        forward, reverse = entities[category]
    else:
        if category == 'iso':
            forward = sublime.decode_value(sublime.load_resource('Packages/' + package_name + '/IsoEntities.json'))
        elif category == 'html':
            forward = sublime.decode_value(sublime.load_resource('Packages/' + package_name + '/HtmlEntities.json'))
        reverse = dict((v, k) for k, v in forward.items())
        entities[category] = (forward, reverse)

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
    return sublime.cache_path() + '/' + package_name + '/'


def getTarGzPath():
    return getDocphpPath() + 'language/php_manual_' + language + '.tar.gz'


def getI18nCachePath():
    return getDocphpPath() + 'language/' + language + '/'


def getTarHandler():
    tarGzPath = getTarGzPath()

    try:
        tar = openfiles[tarGzPath]
    except KeyError:
        tar = tarfile.open(tarGzPath)
        openfiles[tarGzPath] = tar
    return tar


def loadLanguage():
    global docphp_languages
    tarGzPath = getTarGzPath()

    if not os.path.isfile(tarGzPath):
        return False

    tar = getTarHandler()
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
    if not use_language:
        global language
    else:
        language = use_language

    if language not in docphp_languages and not loadLanguage():
        if fallback:
            begin = 'The fallback'
        else:
            begin = 'The'
        sublime.error_message(
            begin + ' language "' + language + '" has not yet installed.\nYou can use\n\n   DocPHP: checkout language\n\ncommand to checkout a language pack.')
        return None, False

    symbol = symbol.lower()
    symbolList = docphp_languages[language]["symbolList"]

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
    elif symbol not in docphp_languages[language]["definition"]:
        output = getSymbolFromHtml(symbol)

        output = decodeEntity(output)
        docphp_languages[language]["definition"][symbol] = output
    return symbol, docphp_languages[language]["definition"][symbol]


def getSymbolFromHtml(symbol):

    tar = getTarHandler()

    member = tar.getmember(docphp_languages[language]["symbolList"][symbol])
    f = tar.extractfile(member)
    output = f.read().decode(errors='ignore')

    output = re.sub('[\s\S]+?(<div[^<>]+?id="'+re.escape(symbol)+'"[\s\S]+?)<div[^<>]+?class="manualnavbar[\s\S]+', '\\1', output)
    dic = {
        '&mdash;': '--',
        '&quot;': "'",
        '<br>': '',
        '&#039;': "'",
        '&$': "&amp;$",
        '&raquo;': '>>',
    }
    pattern = "|".join(map(re.escape, dic.keys()))

    output = re.sub(pattern, lambda m: dic[m.group()], output)

    return output


def formatContent(content, use_panel=False, symbol=False):
    if use_panel:
        content = re.sub('\s+', ' ', content)
        content = re.sub('<(br\s*/?|/p|/div|/li|(div|p)\s[^<>]*|(div|p))>', '\n', content)
        content = re.sub('<.*?>', '', content)
        content = re.sub('\s+\n\s*\n\s+', '\n\n', content)
        content = re.sub('^\s+', '', content, count=1)
        content = decodeEntity(content, 'html')
    else:
        if not isinstance(content, str):
            return

        to = '\\1\\2\\3<br><a href="history.back">back</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="http://php.net/manual/' + \
            language + '/' + symbol + '.php">online</a>'
        languages = getSetting('languages')
        if len(languages) > 1:
            to += '&nbsp;&nbsp;&nbsp;&nbsp;Change language:'
            for lang in getSetting('languages'):
                to += ' <a href="changeto.' + lang + '">' + lang + '</a>'
        content = re.sub('(<h[1-6][^<>]*>)(.*?)(</h[1-6][^<>]*>)', to, content, count=1)
        content = re.sub('<(/?)(blockquote|tr|li|ul|dl|dt|dd|table|tbody|thead)\\b', '<\\1div', content)
        content = re.sub('<(/?)(td)\\b', '<\\1span', content)
        content = re.sub('(?<=</h[1-6]>)', '<div class="horizontal-rule"></div>', content)
        content = '<style>'+sublime.load_resource('Packages/' + package_name + '/style.css') + \
            '</style><div id="outer"><div id="container">' + content + "</div></div>"
    return content


class DocphpShowDefinitionCommand(sublime_plugin.TextCommand):
    history = []
    currentSymbol = ''

    def run(self, edit, symbol=None, force=False):
        global language, currentView
        view = self.view
        currentView = view

        window = view.window()
        language = getSetting('language')

        selection = view.sel()

        if not force and not view.score_selector(selection[0].a, 'source.php'):
            return

        region = view.word(selection[0])

        if symbol == None:
            symbol = view.substr(region)
        symbol = symbol.replace('_', '-')

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

                m = re.search('changeto\.(.*)', url)
                if m:
                    symbol, content = getSymbolDescription(self.currentSymbol, m.group(1))
                else:
                    if url == 'history.back':
                        symbol = self.history.pop()
                        self.currentSymbol = symbol

                    else:
                        self.history.append(self.currentSymbol)
                        symbol = url[:url.find('.html')]
                        self.currentSymbol = symbol
                    symbol, content = getSymbolDescription(symbol)


                content = formatContent(content, symbol=symbol)

                # It seems sublime will core when the output is too long
                # In some cases the value can set to 76200, but we use a 65535 for safety.
                content = content[:65535]
                view.update_popup(content)

            width, height = view.viewport_extent()
            output = formatContent(output, symbol=symbol)

            view.show_popup(
                output,
                flags=sublime.COOPERATE_WITH_AUTO_COMPLETE | sublime.HTML,
                location=-1,
                max_width=min(getSetting('popup_max_width'), width),
                max_height=min(getSetting('popup_max_height'), height),
                on_navigate=on_navigate,
                on_hide=on_hide
            )

            return
        else:
            output = formatContent(symbolDescription, True)
            name = 'docphp'

            panel = window.get_output_panel(name)
            window.run_command("show_panel", {"panel": "output."+name})
            panel.set_read_only(False)
            panel.insert(edit, panel.size(), output + '\n')
            panel.set_read_only(True)


def installLanguagePopup(languageName=None, set_fallback=False, is_init=False):
    global downloading
    if downloading:
        sublime.message_dialog('Another progress is working for checkout ' + downloading + '. Please try again later.')
        return
    languageNameList, languageList, index = getLanguageList(languageName)

    def updateLanguage(index=None):
        if index == -1:
            return
        languageName = languageNameList[index]
        languagePath = getDocphpPath() + 'language/' + languageName

        def checkoutLanguage():
            global language
            if not downloadLanguageGZ(languageName):
                if getSetting('debug'):
                    print('download error')
                return False

            setSetting('language', languageName)
            language = languageName
            languageSettings = currentSettings.get('languages')

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
        currentView.window().show_quick_panel(languageList, updateLanguage, sublime.KEEP_OPEN_ON_FOCUS_LOST)


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
                    sublime.status_message(package_name + ': %.0f%% checking out %s' % (percent, name,))
                else:
                    kb = readsofar / 1024
                    sublime.status_message(package_name + ': %.0f KB checking out %s' % (kb, name,))
        finally:
            outputfile.close()
            downloading = False
        if totalsize and readsofar != totalsize:
            return False
        else:
            return True

    except (urllib.error.HTTPError) as e:
        err = '%s: HTTP error %s contacting API' % (__name__, str(e.code))
    except (urllib.error.URLError) as e:
        err = '%s: URL error %s contacting API' % (__name__, str(e.reason))
    except Exception as e:
        err = e.__class__.__name__

    sublime.message_dialog('Language ' + name + ' checkout failed. Please try again.')

    if getSetting('debug'):
        print(err)
    return


class DocphpCheckoutLanguageCommand(sublime_plugin.TextCommand):

    def run(self, edit, languageName=None):
        view = self.view
        global currentView
        currentView = view

        installLanguagePopup(languageName)


class DocphpSelectLanguageCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        global currentView
        view = self.view
        currentView = view

        languageNameListAll, languageListAll, index = getLanguageList()
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
                loadLanguage()

        currentView.window().show_quick_panel(languageList, selectLanguageCallback)


class DocphpOpenManualIndexCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        self.view.run_command('docphp_show_definition', {"symbol": 'index', "force": True})


class DocphpSearchCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        global currentView
        view = self.view
        currentView = view
        tar = getTarHandler()

        files = []
        for tarinfo in tar.getmembers():
            m = re.search('^.*?/(.*)\.html$', tarinfo.name)
            if m:
                files.append(m.group(1).replace('-', '_'))
        files.sort()

        def show(index):
            if index != -1:
                currentView.run_command('docphp_show_definition', {"symbol": files[index], "force": True})

        currentView.window().show_quick_panel(files, show, sublime.KEEP_OPEN_ON_FOCUS_LOST)


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
