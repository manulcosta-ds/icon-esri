# ArcGIS Icon Browser

A Figma plugin to browse and insert icons from your published ArcGIS icon library.

## Features

- **JSON Metadata Import**: Load your icon metadata file containing component keys
- **Category Filtering**: Browse icons by category (context)
- **Size Filtering**: Filter by icon size (16px, 32px, etc.)
- **Search**: Quick search by icon name
- **Single-Click Insert**: Click any icon to instantly insert it at viewport center
- **Multi-Select**: Hold Shift/Ctrl/Cmd to select multiple icons, then insert all at once
- **Calcite Design System**: UI styled to match ESRI's design language

## Installation

1. Unzip the plugin folder
2. In Figma: **Plugins** → **Development** → **Import plugin from manifest...**
3. Select the `manifest.json` file from the unzipped folder

## Prerequisites

Before using this plugin, you must:

1. **Publish your icon library** in Figma
2. **Enable the library** in the file where you want to use icons
3. **Have a JSON metadata file** with your icon data including `component_key` for each icon

## JSON Format

The plugin expects a JSON array with icon objects. Each object must have:

```json
{
  "id": "unique-id",
  "context": "CategoryName",
  "context_key": "category-key",
  "icon_name": "IconDisplayName",
  "icon_key": "icon-slug",
  "size": 16,
  "component_key": "abc123...",  // Required! From Figma library
  "component_id": "1:234",
  "component_name": "IconName16"
}
```

## Usage

1. Run the plugin
2. Drop your JSON metadata file onto the import area (or click to browse)
3. Browse categories in the left sidebar
4. Use search and size filters to find specific icons
5. **Click** an icon to insert it immediately
6. **Shift/Ctrl/Cmd + Click** to select multiple icons, then click "Insert Selected"

## Keyboard Shortcuts

- **Escape**: Clear selection
- **Cmd/Ctrl + A**: Select all visible icons

## Troubleshooting

**"Could not import icon"**
- Make sure the icon library is published and enabled in your current file
- Go to **Assets** panel → **Team Library** (book icon) → Enable your icon library

**"No icons with component_key found"**
- Your JSON file must include `component_key` for each icon
- This is the hash Figma assigns when you publish components to a library

## Files

- `manifest.json` - Plugin configuration
- `code.js` - Main plugin logic
- `code.ts` - TypeScript source
- `ui.html` - User interface

---

Made with ❤️ for the Calcite Design System
