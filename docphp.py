import sublime, sublime_plugin
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

docphp_languages = {};
entities = {};
currentView = False;
currentSettings = None;

language = '';

def plugin_loaded():
    global currentSettings;
    currentSettings = sublime.load_settings('docphp.sublime-settings');
    sublime.save_settings('docphp.sublime-settings');

def plugin_unloaded():
    sublime.save_settings('docphp.sublime-settings');

def getSetting( key ):
    global currentView, currentSettings;

    local = 'docphp.' + key
    settings = currentView.settings();
    if settings:
        return settings.get( local, currentSettings.get( key, 'not found' ) );
    else:
        return currentSettings.get( key );

def generateEntities():
    global entities;

    def generate():
        entitiesLocal = {};
        for entitiesFile in glob.glob(getI18nSvnPath() + '*.ent'):
            with open(entitiesFile, 'r', -1, 'utf8') as f:
                entitiesText = f.read(10485760);
            matches = re.findall("^<!ENTITY\s+([a-zA-Z0-9._-]+)\s+(['\"])([\s\S]*?)\\2>$", entitiesText, re.MULTILINE);
            for match in matches:
                key, quote, content = match;
                entitiesLocal[key] = re.sub(' xmlns="[^"]+"', '', content);
        return entitiesLocal;

    entities[language] = getJsonOrGenerate('entities', generate);

def parseEntity(match):
    entity = match.group(1);
    if entity not in entities[language]:
        return " <b>" + entity.upper() + "</b> ";
    else:
        return entities[language][entity];

def decodeEntity(xml):
    if language not in entities:
        generateEntities();
    i = 10;
    while i:
        i -= 1;
        newxml = re.sub('&([a-zA-Z0-9._-]+);', parseEntity, xml);
        if newxml == xml:
            break;
        else:
            xml = newxml;
    return xml;

def getDocphpPath():
    return sublime.cache_path() + '/docphp/';

def getTarGzPath():
    return sublime.cache_path() + '/docphp/language/php_manual_' + language + '.tar.gz';

def getI18nCachePath():
    return sublime.cache_path() + '/docphp/language/' + language + '/';

def getI18nSvnPath():
    return sublime.cache_path() + '/docphp/language/' + language + '/phpdoc/';

def loadLanguage():
    global docphp_languages;

    if not getSetting('use_svn'):
        if not os.path.isfile(getTarGzPath()):
            return False;

        def generate():
            symbols = {};
            tarGzPath = getTarGzPath();

            with tarfile.open(tarGzPath) as tar:

                for tarinfo in tar:
                    m = re.search('^php-chunked-xhtml/(.*)\.html$', tarinfo.name);
                    if m:
                        symbols[m.group(1)] = m.group(0);
            return symbols;

        symbols = getJsonOrGenerate('packed_symbols', generate);
        docphp_languages[language] = {"symbolList": symbols, "definition": {}};


        return True;

    if not os.path.isdir(getI18nSvnPath()):
        return False;

    def generate():
        functions = {};
        i18nPath = getI18nSvnPath();
        pathLen = len(i18nPath);
        for root, dirnames, filenames in os.walk(i18nPath):
            if re.search('functions$', root):
                for xmlFile in filenames:
                    for name in re.findall('^(.+)\.xml$', xmlFile):
                        functions[name] = os.path.join(root[pathLen:], xmlFile);
        return functions;

    functions = getJsonOrGenerate('functions', generate);
    docphp_languages[language] = {"symbolList": functions, "definition": {}};
    return True;

def getJsonOrGenerate(name, callback):
    filename = getI18nSvnPath() + '../' + name + '.json';
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf8') as f:
            json = f.read(10485760);
        content = sublime.decode_value(json);

    else:
        content = callback();

        dirname = os.path.dirname(filename);
        if not os.path.isdir(dirname):
            os.makedirs(dirname);
        with open(filename, 'w', encoding="utf8") as f:
            f.write(sublime.encode_value(content));

    return content;

def getSymbolDescription(symbol, only_function = True):

    if language not in docphp_languages and not loadLanguage():
        sublime.error_message('The language "' + language + '" not installed\nYou can use\n\n   docphp: checkout language\n\nto checkout a language pack');
        return None, False;
    if only_function and not getSetting('use_svn'):
        symbol = 'function.' + symbol
    if symbol not in docphp_languages[language]["symbolList"]:
        return None, None;
    else:

        if symbol not in docphp_languages[language]["definition"]:
            if not getSetting('use_svn'):
                output = ''
                path = getI18nCachePath() + 'php-chunked-xhtml/';
                filename = path + symbol + '.html'
                if os.path.isfile(filename):
                    with open(filename, 'r', encoding='utf8', errors='ignore') as f:
                        output = f.read()
                else:

                    with tarfile.open(getTarGzPath()) as tar:
                        member = tar.getmember(docphp_languages[language]["symbolList"][symbol])
                        f=tar.extractfile(member)
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
                        output = re.sub('(<h[1-6][^<>]*>)([^<>]*)(</h[1-6][^<>]*>)', '\\1<a href="http://php.net/manual/'+language+'/'+symbol+'.php">\\2</a><br>\\3<a href="history.back">back</a>', output, count=1)

                        output = '<style>#container{margin:10px}</style><div id="container">' + output + "</div>";

                        if not os.path.isdir(path):
                            os.makedirs(path);
                        with open(filename, 'wb') as f:
                            f.write(output.encode())


            else:

                defFile = docphp_languages[language]["symbolList"][symbol];

                with open(getI18nSvnPath() + defFile, 'r', encoding='utf8') as f:
                    xml = f.read(10485760);
                xml = re.sub(' xmlns="[^"]+"', '', xml, 1);
                xml = decodeEntity(xml);
                xml = re.sub(' xlink:href="[^"]+"', '', xml);
                try:
                    root = ET.fromstring(xml);
                except ET.ParseError as e:
                    if getSetting('debug'):
                        print(xml);
                        raise e;
                    sublime.error_message('Cannot read definition of ' + symbol + ', please report this issue on github');
                    return None, False;
                output = '';

                refsect1 = root.find('refsect1[@role="description"]');
                if not refsect1:
                    refsect1 = root.find('refsect1');

                methodsynopsis = refsect1.find('methodsynopsis');

                if not methodsynopsis:
                    methodsynopsis = root.find('refsect1/methodsynopsis');

                output += '<type>' + methodsynopsis.find('type').text + '</type> <b style="color:#369">' + symbol + "</b> (";
                hasPrviousParam = False;
                for methodparam in methodsynopsis.findall('methodparam'):

                    output += ' ';
                    attrib = methodparam.attrib;
                    opt = False;
                    if "choice" in attrib and attrib['choice'] == 'opt':
                        opt = True;
                        output += "[";
                    if hasPrviousParam:
                        output += ", ";
                    output += '<type>' + methodparam.find('type').text + "</type> $" + methodparam.find('parameter').text;
                    if opt:
                        output += "]";
                    hasPrviousParam = True;
                output += " )\n";

                # output += root.find('refnamediv/refpurpose').text.strip() + "\n\n";

                for para in refsect1.findall('para'):
                    output += "   " + re.sub("<.*?>", "", re.sub("<row>([\s\S]*?)</row>", "\\1<br>", re.sub("\s\s+", " ", ET.tostring(para, 'utf8', 'html').decode()))) + "\n";

                output += "\n";

                variablelist = root.findall('refsect1[@role="parameters"]/para/variablelist/varlistentry');
                for variable in variablelist:
                    output += ET.tostring(variable.find('term/parameter'), 'utf8', 'html').decode() + " :\n";
                    for para in variable.findall('listitem/para'):
                        # TODO: parse table
                        output += "   " +re.sub("<row>([\s\S]*?)</row>", "\\1<br>", re.sub("\s\s+", " ", ET.tostring(para, 'utf8', 'html').decode())) + "\n";
                    output += "\n";
                output += "\n";

                returnvalues = root.findall('refsect1[@role="returnvalues"]/para');
                for para in returnvalues:
                    output += re.sub("\s\s+", " ", ET.tostring(para, 'utf8', 'html').decode()).strip() + "\n";

            docphp_languages[language]["definition"][symbol] = output;
        return symbol, docphp_languages[language]["definition"][symbol];

class DocphpShowDefinitionCommand(sublime_plugin.TextCommand):
    history = [];
    currentSymbol = '';

    def run(self, edit):
        global language, currentView;
        view = self.view;
        currentView = view;

        window = view.window();
        language = getSetting('language');

        selection = view.sel();
        if not re.search('source\.php', view.scope_name(selection[0].a)):
            return;
        selectionBackup = list(selection);

        view.run_command('expand_selection', {"to": "word"});

        symbol = view.substr(selection[0]).replace('_', '-');
        selection.clear();
        selection.add_all(selectionBackup);

        # symbol = 'basename'

        symbol, symbolDescription = getSymbolDescription(symbol);
        if symbolDescription == None:
            if getSetting('prompt_when_not_found'):
                view.show_popup('not found')
            return;
        if symbolDescription == False:
            return;

        if getSetting('use_panel') == False:
            output = symbolDescription
            if getSetting('use_svn'):
                output = re.sub('\n', '<br>\n', symbolDescription);
                output = re.sub('<parameter>', '<parameter style="color:#369;font-weight:900"><b>', output)
                output = re.sub('</parameter>', '</b></parameter>', output)
                output = re.sub('<type>', '<type style="color:#369">', output)
            if getSetting('debug'):
                print(output)

            self.currentSymbol = symbol;
            def on_hide():
                self.currentSymbol = '';
                self.history = [];

            def on_navigate(url):
                if url[:4] == 'http':
                    webbrowser.open_new(url)
                    return True;

                if url == 'history.back':
                    symbol = self.history.pop()
                    self.currentSymbol = symbol

                else:
                    self.history.append(self.currentSymbol)
                    symbol = url[:url.find('.html')];
                    self.currentSymbol = symbol;

                # It seems sublime will core when the output is too long
                # In some cases the value can set to 76200, but we use a 65535 for safety.
                symbol, content = getSymbolDescription(symbol, only_function = False)[:65535];
                view.update_popup(content)
            view.show_popup(output, location = -1,
                    max_width = getSetting('popup_max_width'), max_height = getSetting('popup_max_height'),
                    on_navigate = on_navigate, on_hide = on_hide)
            return;
        else:
            output = re.sub('<.*?>', '', symbolDescription);
            name = 'docphp';

            panel = window.get_output_panel(name);
            window.run_command("show_panel", {"panel": "output."+name})
            panel.set_read_only(False)
            panel.insert(edit, panel.size(), output + '\n')
            panel.set_read_only(True)



def installLanguagePopup():
    languages = {};
    for path in glob.glob(getDocphpPath() + 'language/*'):
        match = re.search('docphp/language.([a-zA-Z]{2}(_[a-zA-Z]{2}){0,1})$', path);
        if match:
            languages[match.group(1)] = path;
    languageList = list(languages);

    def updateLanguage(index):
        if index == -1:
            return;
        languageName = languageList[index];
        languagePath = languages[languageName];

        def checkoutLanguage():
            if getSetting('use_svn'):
                sublime.status_message('checking out ' + languageName);

                p = runCmd('svn', ['checkout', 'http://svn.php.net/repository/phpdoc/' + languageName + '/trunk', 'phpdoc_svn'], languagePath);
                out, err = p.communicate();
                if p.returncode == 0:
                    if os.path.isdir(languagePath + '/phpdoc'):
                        shutil.rmtree(languagePath + '/phpdoc');

                    os.rename(languagePath + '/phpdoc_svn', languagePath + '/phpdoc');
                    sublime.message_dialog('Language ' + languageName + ' is checked out');
                    selectLanguage(languageName)
                else:
                    if getSetting('debug'):
                        print(out);
                        print(err);
                    shutil.rmtree(languagePath + '/phpdoc_svn');
            else:

                if downloadLanguageGZ(languageName):
                    sublime.message_dialog('Language ' + languageName + ' is checked out');
                    selectLanguage(languageName);
                else:
                    if getSetting('debug'):
                        print('download error')

        sublime.set_timeout_async(checkoutLanguage, 0);

    currentView.window().show_quick_panel(languageList, updateLanguage);

def downloadLanguageGZ(name):
    err = None;
    try:
        url = 'http://php.net/distributions/manual/php_manual_' + name + '.tar.gz'

        filename = getDocphpPath() + 'language/php_manual_' + name + '.tar.gz';

        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)

        gziped = response.read(16777216);

        with open(filename, 'wb') as handle:
            handle.write(gziped);

        return True;

    except (urllib.error.HTTPError) as e:
        err = '%s: HTTP error %s contacting API' % (__name__, str(e.code))
        if e.code == 404:
            sublime.message_dialog('Language ' + name + ' MUST checkout by SVN. Please check your settings.');
            return False;

    except (urllib.error.URLError) as e:
        err = '%s: URL error %s contacting API' % (__name__, str(e.reason))
    except Exception as e:
        err = e.__class__.__name__

    sublime.message_dialog('Language ' + name + ' checkout failed. Please try again.');

    if getSetting('debug'):
        print(err);
    return;

def runCmd(binType, params, cwd = None):
    binary = getSetting(binType + '_bin');
    params.insert(0, binary);
    if not os.path.isfile(binary) and binary != binType:
        sublime.error_message("Can't find " + binary + " binary file at " + binary);
        return False;

    try:
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, shell=False, startupinfo=startupinfo)
        else:
            p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, shell=False)
        return p;

    except FileNotFoundError:
        message = 'Cannot run ' + binType + ' command, please check your settings.';
        if binType == 'svn':
            message += '\n\nSVN is needed by DocPHP for checking out language packs.';
        sublime.error_message(message);
        return False;

class DocphpCheckoutLanguageCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view;
        global currentView;
        currentView = view;
        docphpPath = getDocphpPath();
        if not os.path.isdir(docphpPath):
            os.makedirs(docphpPath);
        installLanguagePopup();

def selectLanguage(name):
    currentSettings.set('language', name);
    sublime.save_settings('docphp.sublime-settings');
    currentView.settings().set('docphp.language', name);

class DocphpSelectLanguageCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global currentView, language;
        view = self.view;
        currentView = view;

        languages = [];
        for path in glob.glob(getDocphpPath() + 'language/*'):
            match = re.search('docphp/language.([a-zA-Z]{2}(_[a-zA-Z]{2}){0,1})$', path);
            if match:
                if os.path.isdir(path + '/phpdoc'):
                    languages.append(match.group(1));

        def selectLanguageCallback(index):
            if index != -1:
                language = languages[index];
                selectLanguage(language)

        currentView.window().show_quick_panel(languages, selectLanguageCallback);
