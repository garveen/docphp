## DocPHPManualer for Sublime Text 3

show the document of current function on Sublime Text

<img src="https://raw.github.com/acabin/docphp/screenshots/screenshots/popup.png" alt="Popup manual" width="956">

### Usage

This package will show a list of available languages after installed, which you may select the one you are using from it. If you want you change language pack later, please use the `DocPHP: checkout language` command. All these operations will take a few minutes depends on your Internet connection.

The default hotkey is `ctrl + alt + d`.

##### Note:

DocPHPManualer will generate cache files, which usually located at SUBLIME_PATH/Data/Cache/DocPHPManualer. These cache files should be removed automatically when removing the package.

### Settings

```javascript
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
