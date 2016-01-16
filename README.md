## DocPHPManualer for Sublime Text 3

show the document of current function on Sublime Text

<img src="https://raw.github.com/acabin/docphp/screenshots/screenshots/popup.png" alt="Popup manual" width="956">

### Usage

This package will automatically download the Engish language pack after installed. If you want you use a language other than English, please follow suggestions blow:

First, use the `checkout language` command for which you are using, and this will take a few minutes depends on your Internet connection. Then when you pointed to a function name, press `ctrl + alt + d`, and see what's happening!

Note:

DocPHPManualer will generate cache files, which usually located at SUBLIME_PATH/Data/Cache/docphp. You may need to remove these files manually in case uninstall DocPHPManualer completely.

### Settings

```json
{
	"debug": false,
	"language": false,
	"language_fallback": false,
	"languages": {},
	"popup_max_height": 480,
	"popup_max_width": 640,
	"prompt_when_not_found": true,
	"svn_bin": "svn",
	"use_panel": false
}
```

##### Note:

`svn_bin` is used when a language pack's download is failed.

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
