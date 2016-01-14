## DocPHPManualer for Sublime Text 3

show the document of current function on Sublime Text

![popup](/screenshots/1.png?raw=true "Document in popup")

![panel](/screenshots/2.png?raw=true "Document in panel")

### Usage

You should have subversion installed on your machine. SVN is used for checkout the official document.

First, use the `checkout language` command for which you are using, and this will take a few minutes depends on your Internet connection. Then when you pointed to a function name, press `ctrl + alt + d`, and see what's happening!

Note:

DocPHPManualer will generate cache files, which usually located at SUBLIME_PATH/Data/Cache/docphp. You may need to remove these files manually in case uninstall DocPHPManualer completely.

### Settings

```json
{
	"debug": false,
	"language": "en",
	"prompt_when_not_found": true,
	"svn_bin": "svn",
	"use_panel": false
}
```

### Commands

```json
[
    {"caption": "DocPHP: show definition", "command": "docphp_show_definition"},
    {"caption": "DocPHP: checkout language", "command": "docphp_checkout_language"},
    {"caption": "DocPHP: select language", "command": "docphp_select_language"},
]
```

### Hotkey

```json
[
	{ "keys": ["ctrl+alt+d"], "command": "docphp_show_definition"}
]
```
