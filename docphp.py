import sublime, sublime_plugin
import xml.etree.ElementTree as ET
import re
import os
import subprocess
import glob
import shutil

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
    return currentView.settings().get( local, currentSettings.get( key, 'not found' ) )

def generateEntities():
    global entities;

    def generate():
        entitiesLocal = {};
        for entitiesFile in glob.glob(getI18nPath() + '*.ent'):
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

def getI18nPath():
    return sublime.cache_path() + '/docphp/language/' + language + '/phpdoc/';

def loadLanguage():
    global docphp_languages;

    if not os.path.isdir(getI18nPath()):
        return False;

    def generate():
        functions = {};
        i18nPath = getI18nPath();
        pathLen = len(i18nPath);
        for root, dirnames, filenames in os.walk(i18nPath):
            if re.search('functions$', root):
                for xmlFile in filenames:
                    for name in re.findall('^(.+)\.xml$', xmlFile):
                        functions[re.sub('-', '_', name)] = os.path.join(root[pathLen:], xmlFile);
        return functions;

    functions = getJsonOrGenerate('functions', generate);
    docphp_languages[language] = {"symbolList": functions, "definition": {}};
    return True;

def getJsonOrGenerate(name, callback):
    filename = getI18nPath() + name + '.json';
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

def getSymbolDescription(symbol):

    if language not in docphp_languages and not loadLanguage():
        sublime.error_message('The language "' + language + '" not installed\nYou can use\n\n   docphp: checkout language\n\nto checkout a language pack');
        return False;

    if symbol not in docphp_languages[language]["symbolList"]:
        return None;
    else:

        if symbol not in docphp_languages[language]["definition"]:
            defFile = docphp_languages[language]["symbolList"][symbol];

            with open(getI18nPath() + defFile, 'r', encoding='utf8') as f:
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
                return False;
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
        return docphp_languages[language]["definition"][symbol];

class DocphpShowDefinitionCommand(sublime_plugin.TextCommand):
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

        symbol = view.substr(selection[0]);
        selection.clear();
        selection.add_all(selectionBackup);

        # symbol = 'basename'

        symbolDescription = getSymbolDescription(symbol);
        if symbolDescription == None:
            if getSetting('prompt_when_not_found'):
                sublime.message_dialog('not found');
            return;
        if symbolDescription == False:
            return;

        if getSetting('use_panel') == False:
            output = re.sub('\n', '<br>\n', symbolDescription);
            output = re.sub('<parameter>', '<parameter style="color:#369;font-weight:900"><b>', output)
            output = re.sub('</parameter>', '</b></parameter>', output)
            output = re.sub('<type>', '<type style="color:#369">', output)
            if getSetting('debug'):
                print(output)
            view.show_popup(output, location = -1,
                    max_width = 640, max_height = 480,
                    on_navigate = None, on_hide = None)
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

        sublime.set_timeout_async(checkoutLanguage, 0);

    currentView.window().show_quick_panel(languageList, updateLanguage);



def initLanguage():
    docphpPath = getDocphpPath();
    p = runCmd('svn', ['checkout', 'http://svn.php.net/repository/phpdoc', 'language_svn', '--depth=immediates'], docphpPath);
    out, err = p.communicate();
    if p.returncode == 0:
        os.rename(docphpPath + 'language_svn', docphpPath + 'language');
        installLanguagePopup();
    else:
        print(out);
        shutil.rmtree(getDocphpPath() + 'language_svn')


def runCmd(binType, params, cwd = None):
    binary = getSetting(binType + '_bin');
    params.insert(0, binary);
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

        svn_bin = getSetting('svn_bin');

        if not os.path.isfile(svn_bin) and not svn_bin == "svn":
            sublime.error_message("Can't find SVN binary file at "+svn_bin);
            return False;

        docphpPath = getDocphpPath();
        if not os.path.isdir(docphpPath):
            os.makedirs(docphpPath);

        p = runCmd('svn', []);
        if not p:
            return;
        if not os.path.isdir(docphpPath + 'language'):
            sublime.set_timeout_async(initLanguage, 0);
            sublime.status_message('init language list...');
        else:
            installLanguagePopup()
        return;

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
