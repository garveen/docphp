import sublime
import sublime_plugin
import re
import os
import shutil
import tarfile
import webbrowser
import time
import urllib
from Default import symbol as sublime_symbol
from html.parser import HTMLParser

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


def plugin_loaded():
    global currentSettings, language, currentView
    currentSettings = sublime.load_settings(setting_file)
    language = currentSettings.get('language')
    currentView = sublime.active_window().active_view()

    docphpPath = getDocphpPath()
    if not os.path.isdir(docphpPath + 'language'):
        os.makedirs(docphpPath + 'language')

    if not callable(sublime_symbol.symbol_at_point) or not callable(sublime_symbol.navigate_to_symbol):
        sublime.error_message('Cannot find symbol_at_point from Default.sublime-package\n\nPlease restore the file which usually replaced by outdated localizations')

    from package_control import events

    if events.install(package_name) or not language:
        currentView.run_command('docphp_checkout_language', {"is_init": True, "set_fallback": True})


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


def getAllLanguages():
    return sublime.decode_value(sublime.load_resource('Packages/' + package_name + '/languages.json'))


def getLanguageList(languageName=None, format='all', getAll=True):
    if not getAll:
        languageName = getSetting('languages')

    if languageName == None:
        dic = []
    elif isinstance(languageName, str):
        dic = [languageName]
    else:
        dic = languageName

    languages = getAllLanguages()
    languages = [(k, languages[k]) for k in sorted(languages.keys())]
    languageList = []
    index = None
    for k, v in languages:
        if languageName == None or k in dic:
            index = len(languageList)
            if format == 'all':
                languageList.append(k + ' ' + v['name'] + ' (' + v['nativeName'] + ')')
            elif format == 'name':
                languageList.append(v['name'])
            elif format == 'nativeName':
                languageList.append(v['nativeName'])
            elif format == 'raw':
                v['shortName'] = k
                languageList.append(v)

    return languageList, index


def decodeEntity(xml, category='iso'):
    global entities
    if not isinstance(xml, str):
        return xml
    if entities[category]:
        forward, reverse = entities[category]
    else:
        resourceMap = {
            "iso": "IsoEntities.json",
            "html": "HtmlEntities.json",
        }
        forward = sublime.decode_value(sublime.load_resource('Packages/' + package_name + '/' + resourceMap[category]))

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


def getI18nCachePath(languageName=None):
    if not languageName:
        languageName = language
    return getDocphpPath() + 'language/' + languageName + '/'


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


def languageExists(languageName=None, fallback=False):
    if not languageName:
        languageName = language
    if not language:
        currentView.run_command('docphp_checkout_language', {"is_init": True, "set_fallback": True})
        return False
    if languageName not in docphp_languages and not loadLanguage():
        if fallback:
            begin = 'The fallback'
        else:
            begin = 'The'
        print(getAllLanguages())
        show_name = getAllLanguages()[languageName]['name']
        sublime.error_message(begin + ' language "' + show_name +
                              '" has not yet installed.\nYou can use\n\n   DocPHP: checkout language\n\ncommand to checkout a language pack.')
        return False
    return True


def getSymbolDescription(symbol, use_language=False, fallback=False):
    if not use_language:
        global language
    else:
        language = use_language

    if not languageExists(language, fallback):
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

        docphp_languages[language]["definition"][symbol] = output
    return symbol, docphp_languages[language]["definition"][symbol]


def getSymbolFromHtml(symbol):

    tar = getTarHandler()

    member = tar.getmember(docphp_languages[language]["symbolList"][symbol])
    f = tar.extractfile(member)
    output = f.read().decode(errors='ignore')

    dic = {
        '&mdash;': chr(8212),
        '&quot;': '"',
        '<br>': '',
        '&#039;': "'",
        '&$': "&amp;$",
        '&raquo;': chr(187),
    }
    pattern = "|".join(map(re.escape, dic.keys()))

    output = re.sub(pattern, lambda m: dic[m.group()], output)

    return output


class DocphpShowDefinitionCommand(sublime_plugin.TextCommand):
    history = []
    currentSymbol = ''
    projectSymbols = []
    window = False
    projectView = False

    def is_enabled(self, **args):
        selection = self.view.sel()
        force = args.get('force')

        if force or self.view.score_selector(selection[0].a, 'source.php'):
            return True
        else:
            return False

    def want_event(self):
        return True

    def run(self, edit, event=None, symbol=None, force=False):
        global language, currentView
        view = self.view
        currentView = view
        pt = False

        language = getSetting('language')

        if not language:
            view.window().run_command('docphp_checkout_language')
            return

        if symbol == None:
            if event:
                pt = view.window_to_text((event["x"], event["y"]))
            else:
                pt = view.sel()[0]
            self.pt = pt
            symbol, locations = sublime_symbol.symbol_at_point(view, pt)

        translatedSymbol = symbol.replace('_', '-')

        # symbol = 'basename'

        translatedSymbol, symbolDescription = getSymbolDescription(translatedSymbol)

        if symbolDescription == None:
            if self.search_in_scope(symbol):
                return
            if getSetting('search_user_symbols') and len(locations):
                sublime_symbol.navigate_to_symbol(view, symbol, locations)
                return
            if getSetting('prompt_when_not_found'):
                view.show_popup('not found', sublime.COOPERATE_WITH_AUTO_COMPLETE)
                return
        if symbolDescription == False:
            return

        if getSetting('use_panel') == False:
            self.show_popup(translatedSymbol, symbolDescription)
        else:
            self.show_panel(translatedSymbol, symbolDescription, edit)

    def search_in_scope(self, symbol):
        search_str = self.view.substr(self.view.line(self.pt))
        if re.search("(\$this\s*->|self\s*::|static\s*::)\s*" + re.escape(symbol), search_str) != None:
            lower = symbol.lower()
            for scopeSymbol in self.view.symbols():
                if scopeSymbol[1].lower() == lower:
                    self.view.sel().clear()
                    self.view.sel().add(scopeSymbol[0])
                    self.view.show(scopeSymbol[0])
                    return True
        return False

    def show_popup(self, symbol, symbolDescription):
        output = symbolDescription

        if getSetting('debug'):
            print(output)

        self.currentSymbol = symbol

        width, height = self.view.viewport_extent()
        output = self.formatPopup(output, symbol=symbol)

        # It seems sublime will core when the output is too long
        # In some cases the value can set to 76200, but we use a 65535 for safety.
        output = output[:65535]

        self.view.show_popup(
            output,
            flags=sublime.COOPERATE_WITH_AUTO_COMPLETE | sublime.HTML,
            location=-1,
            max_width=min(getSetting('popup_max_width'), width),
            max_height=min(getSetting('popup_max_height'), height - 100),
            on_navigate=self.on_navigate,
            on_hide=self.on_hide
        )

    def show_panel(self, symbol, symbolDescription, edit):
        output = self.formatPanel(symbolDescription)
        name = 'docphp'
        window = self.view.window()
        panel = window.get_output_panel(name)
        window.run_command("show_panel", {"panel": "output."+name})
        panel.set_read_only(False)
        panel.insert(edit, panel.size(), output + '\n')
        panel.set_read_only(True)

    def on_hide(self):
        self.currentSymbol = ''
        self.history = []

    def on_navigate(self, url):
        if re.search('^https?://', url):
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

        if content == False:
            return False

        content = self.formatPopup(content, symbol=symbol, can_back=len(self.history) > 0)

        content = content[:65535]
        self.view.update_popup(content)

    def formatPopup(self, content, symbol, can_back=False):
        if not isinstance(content, str):
            return

        content = decodeEntity(content)

        parser = PopupHTMLParser(symbol, language, can_back)
        try:
            parser.feed(content)
        except FinishError:
            pass
        content = parser.output
        content = '<style>'+sublime.load_resource('Packages/' + package_name + '/style.css') + \
            '</style><div id="outer"><div id="container">' + content + "</div></div>"
        return content

    def formatPanel(self, content):
        if not isinstance(content, str):
            return
        content = decodeEntity(content)
        content = re.sub('\s+', ' ', content)
        content = re.sub('<(br\s*/?|/p|/div|/li|(div|p)\s[^<>]*|(div|p))>', '\n', content)
        content = re.sub('<.*?>', '', content)
        content = re.sub('\s+\n\s*\n\s+', '\n\n', content)
        content = re.sub('^\s+', '', content, count=1)
        content = decodeEntity(content, 'html')
        return content


class PopupHTMLParser(HTMLParser):
    symbol = ''
    language = ''
    can_back = False
    stack = []
    output = ''
    as_div = ['blockquote', 'tr', 'li', 'ul', 'dl', 'dt', 'dd', 'table', 'tbody', 'thead']
    strip = ['td']
    started = False
    navigate_rendered = False
    navigate_up = ''

    def __init__(self, symbol, language, can_back):
        self.symbol = symbol
        self.language = language
        self.can_back = can_back
        super().__init__()

    def parseAttrs(self, attrs):
        ret = {}
        for k, v in attrs:
            ret[k] = v
        return ret


    def handle_starttag(self, tag, attrs):
        attrs = self.parseAttrs(attrs)

        for k in attrs:
            v = attrs[k]
            if k == 'id' and v == self.symbol:
                self.output = ''
            if k == 'class' and v == 'up':
                self.output = ''

        if tag in self.as_div:
            if 'class' in attrs:
                attrs['class'] += ' ' + tag
            else:
                attrs['class'] = tag
            tag = 'div'
        if tag in self.strip:
            return

        self.stack.append({'tag': tag, 'attrs': attrs})
        border = self.shall_border(tag, attrs)
        if border:
            self.output += '<div class="border border-' + border + '">'
        self.output += self.get_tag_text(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self.as_div:
            tag = 'div'
        if tag in self.strip:
            return
        try:
            while(True):
                previous = self.stack.pop()
                self.output += '</' + tag + '>'

                if re.search('h[1-6]', tag):
                    self.output += '<div class="horizontal-rule"></div>'
                    if not self.navigate_rendered:
                        self.navigate_rendered = True
                        self.output += ('<a href="history.back">back</a>' if self.can_back else 'back') + '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="http://php.net/manual/' + \
                            self.language + '/' + self.symbol + '.php">online</a>' + \
                            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' + re.sub('.*?(<a.*?</a>).*', '\\1', self.navigate_up)
                        languages, _ = getLanguageList(format='raw', getAll=False)
                        if len(languages) > 1:
                            self.output += '&nbsp;&nbsp;&nbsp;&nbsp;Change language:'
                            for lang in languages:
                                self.output += ' <a href="changeto.' + lang['shortName'] + '">' + lang['nativeName'] + '</a>'

                if self.shall_border(previous['tag'], previous['attrs']):
                    self.output += '</div>'
                for k in previous['attrs']:
                    v = previous['attrs'][k]
                    if k == 'id' and v == self.symbol:
                        raise FinishError
                    if k == 'class' and v == 'up':
                        self.navigate_up = self.output
                if tag == previous['tag']:
                    break

        except IndexError:
            pass

    def handle_startendtag(self, tag, attrs):
        if tag in self.as_div:
            if 'class' in attrs:
                attrs['class'] += ' ' + tag
            else:
                attrs['class'] = tag
            tag = 'div'
        self.output += self.get_tag_text(tag, attrs, True)

    def handle_data(self, data):
        self.output += data
        pass

    def handle_entityref(self, name):
        self.output += '&' + name + ';'

    def handle_charref(self, name):
        self.output += '&' + name + ';'

    def shall_border(self, tag, attrs):
        if tag.lower() not in ['div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            return False
        for k in attrs:
            v = attrs[k]
            if k == 'class':
                if re.search('\\b(phpcode|classsynopsis|methodsynopsis|note|informaltable)\\b', v):
                    return 'gray'
                elif re.search('\\b(tip)\\b', v):
                    return 'blue'
                elif re.search('\\b(warning)\\b', v):
                    return 'pink'
                elif re.search('\\b(caution)\\b', v):
                    return 'yellow'
        return False

    def get_tag_text(self, tag, attrs, is_startend=False):
        return '<' + (tag + ' ' + ' '.join(map(lambda m: m + '="' + re.sub('(?<!\\\\)"', '\\"', attrs[m]) + '"', attrs))).rstrip() + (' />' if is_startend else '>')


class DocphpCheckoutLanguageCommand(sublime_plugin.TextCommand):

    languageList = None
    languageName = None
    downloading = False
    set_fallback = None

    def run(self, edit, languageName=None, set_fallback=False, is_init=False):
        view = self.view
        global currentView
        currentView = view

        if self.downloading:
            sublime.message_dialog('Another progress is working for checkout ' + self.downloading + '. Please try again later.')
            return

        self.languageList, index = getLanguageList(languageName)
        self.set_fallback = set_fallback

        if languageName:
            self.updateLanguage(index)
        else:
            currentView.window().show_quick_panel(self.languageList, self.updateLanguage, sublime.KEEP_OPEN_ON_FOCUS_LOST)

    def updateLanguage(self, index=None):
        if index == -1 or index == None:
            return
        languageName = re.search('^\w+', self.languageList[index]).group(0)

        self.languageName = languageName
        sublime.set_timeout_async(self.checkoutLanguage, 0)

    def checkoutLanguage(self):
        global language
        languageName = self.languageName
        if not self.downloadLanguageGZ(languageName):
            if getSetting('debug'):
                print('download error')
            return False

        setSetting('language', languageName)
        language = languageName
        languageSettings = currentSettings.get('languages')

        languageSettings[languageName] = 'gz'

        setSetting('languages', languageSettings)
        if self.set_fallback:
            setSetting('language_fallback', languageName)

        loadLanguage()

        sublime.message_dialog('Language ' + languageName + ' is checked out')

    def downloadLanguageGZ(self, name):
        err = None
        try:
            url = 'http://php.net/distributions/manual/php_manual_' + name + '.tar.gz'

            filename = getDocphpPath() + 'language/php_manual_' + name + '.tar.gz.downloading'

            response = urllib.request.urlopen(url)
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
                self.downloading = name
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
                self.downloading = False
                if totalsize and readsofar != totalsize:
                    os.unlink(filename)
                    err = 'Download failed'

        except (urllib.error.HTTPError) as e:
            err = '%s: HTTP error %s contacting API' % (__name__, str(e.code))
        except (urllib.error.URLError) as e:
            err = '%s: URL error %s contacting API' % (__name__, str(e.reason))
        except Exception as e:
            err = e.__class__.__name__

        if not err:
            if os.path.isdir(getI18nCachePath(name)):
                shutil.rmtree(getI18nCachePath(name))
            newname = getDocphpPath() + 'language/php_manual_' + name + '.tar.gz'
            if os.path.isfile(newname):
                os.unlink(newname)
            os.rename(filename, newname)
            return True

        print(err)
        sublime.message_dialog('Language ' + name + ' checkout failed. Please try again.')

        return False


class DocphpSelectLanguageCommand(sublime_plugin.TextCommand):

    languageNameList = None

    def run(self, edit):
        global currentView
        view = self.view
        currentView = view

        self.languageList, _ = getLanguageList(getAll=False)

        currentView.window().show_quick_panel(self.languageList, self.selectLanguageCallback)

    def selectLanguageCallback(self, index):
        global language
        if index != -1:
            language = re.search('^\w+', self.languageList[index]).group(0)
            setSetting('language', language)
            loadLanguage()


class DocphpOpenManualIndexCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        global currentView
        currentView = self.view
        self.view.run_command('docphp_show_definition', {"symbol": 'index', "force": True})


class DocphpSearchCommand(sublime_plugin.TextCommand):

    def want_event(self):
        return True

    def run(self, edit, event=None, at_point=False):
        global currentView
        view = self.view
        window = view.window()
        currentView = view
        if not languageExists():
            return
        tar = getTarHandler()
        symbol = None

        if at_point:
            symbol = view.substr(view.word(view.sel()[0]))

        files = list(docphp_languages[language]["symbolList"].keys())
        files.sort()

        def show(index):
            if index != -1:
                currentView.run_command('docphp_show_definition', {"symbol": files[index], "force": True})

        selected_index = -1
        if event:
            pt = view.window_to_text((event["x"], event["y"]))
            symbol, locations = sublime_symbol.symbol_at_point(view, pt)
            for prefix in ['function.', 'book.', 'class.']:
                try:
                    selected_index = files.index(prefix + symbol)
                    break
                except ValueError:
                    pass
        currentView.window().show_quick_panel(files, show, selected_index=selected_index)


class DocPHPListener(sublime_plugin.EventListener):
    prevTime = 0
    delaying = False

    def on_selection_modified_async(self, view):
        if not getSetting('auto'):
            return
        global currentView
        currentView = view
        self.prevTime = time.time()
        if not self.delaying:
            sublime.set_timeout_async(self.doAutoShow, getSetting('auto_delay') + 50)
            self.delaying = True

    def doAutoShow(self):
        delayTime = getSetting('auto_delay')
        if (time.time() - self.prevTime) * 1000 > delayTime:
            self.delaying = False
            if not currentView.is_popup_visible():
                currentView.run_command('docphp_show_definition')
        else:
            sublime.set_timeout_async(self.doAutoShow, int(delayTime - (time.time() - self.prevTime) * 1000) + 50)


class FinishError(Exception):

    """For stopping the HTMLParser"""
    pass
