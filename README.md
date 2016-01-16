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
	// Show manual automatically
	"auto": false,

	// Delay after cursor finish moving, in microseconds
	"auto_delay": 500,

	// Debug mode
	"debug": false,

	// Select language
	"language": false,

	// Select fallback language
	"language_fallback": false,

	// Available languages
	"languages": {},

	// Max height and width of popup
	"popup_max_height": 480,
	"popup_max_width": 640,

	// Prompt "not found" when symbol not found
	"prompt_when_not_found": true,

	// In rare condiction the program may fallback to svn
	"svn_bin": "svn",

	// Use the panel on the bottom instead of popup
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
