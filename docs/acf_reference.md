# ACF JSON Field Reference

## Field Group Structure

```json
{
    "key": "group_unique_id",
    "title": "Field Group Title",
    "fields": [],
    "location": [
        [
            {
                "param": "block",
                "operator": "==",
                "value": "acf/block-name"
            }
        ]
    ],
    "menu_order": 0,
    "position": "normal",
    "style": "default",
    "label_placement": "top",
    "instruction_placement": "label",
    "active": true
}
```

## Common Field Types

### Text Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "text",
    "required": 0,
    "default_value": "",
    "placeholder": "",
    "maxlength": ""
}
```

### Textarea Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "textarea",
    "required": 0,
    "default_value": "",
    "rows": 4,
    "new_lines": "wpautop"
}
```

### WYSIWYG Editor
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "wysiwyg",
    "required": 0,
    "default_value": "",
    "tabs": "all",
    "toolbar": "full",
    "media_upload": 1
}
```

### Image Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "image",
    "required": 0,
    "return_format": "array",
    "preview_size": "medium",
    "library": "all",
    "mime_types": "jpg, jpeg, png, gif, webp"
}
```

### Link Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "link",
    "required": 0,
    "return_format": "array"
}
```

### Select Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "select",
    "required": 0,
    "choices": {
        "option1": "Option 1",
        "option2": "Option 2"
    },
    "default_value": "option1",
    "allow_null": 0,
    "multiple": 0,
    "ui": 1
}
```

### True/False Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "true_false",
    "required": 0,
    "default_value": 0,
    "ui": 1
}
```

### Repeater Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "repeater",
    "required": 0,
    "min": 0,
    "max": 0,
    "layout": "block",
    "button_label": "Add Row",
    "sub_fields": []
}
```

### Group Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "group",
    "required": 0,
    "layout": "block",
    "sub_fields": []
}
```

### Gallery Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "gallery",
    "required": 0,
    "return_format": "array",
    "preview_size": "medium",
    "library": "all",
    "min": 0,
    "max": 0
}
```

### Number Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "number",
    "required": 0,
    "default_value": "",
    "min": "",
    "max": "",
    "step": ""
}
```

### Email Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "email",
    "required": 0,
    "default_value": "",
    "placeholder": ""
}
```

### URL Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "url",
    "required": 0,
    "default_value": "",
    "placeholder": ""
}
```

### Color Picker Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "color_picker",
    "required": 0,
    "default_value": "",
    "enable_opacity": 1
}
```

### Date Picker Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "date_picker",
    "required": 0,
    "display_format": "F j, Y",
    "return_format": "Y-m-d"
}
```

### Post Object Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "post_object",
    "required": 0,
    "post_type": ["post", "page"],
    "taxonomy": [],
    "return_format": "object",
    "multiple": 0,
    "allow_null": 0
}
```

### Relationship Field
```json
{
    "key": "field_unique_id",
    "label": "Field Label",
    "name": "field_name",
    "type": "relationship",
    "required": 0,
    "post_type": ["post"],
    "taxonomy": [],
    "filters": ["search", "post_type", "taxonomy"],
    "return_format": "object",
    "min": 0,
    "max": 0
}
```

## Block Registration (block.json)

```json
{
    "name": "acf/block-name",
    "title": "Block Title",
    "description": "Block description",
    "category": "theme",
    "icon": "admin-comments",
    "keywords": ["keyword1", "keyword2"],
    "acf": {
        "mode": "preview",
        "renderTemplate": "blocks/block-name/block-name.php"
    },
    "supports": {
        "align": true,
        "anchor": true,
        "customClassName": true,
        "jsx": false
    }
}
```

## Key Generation

Keys must be unique and follow the format:
- Field Groups: `group_` followed by a unique identifier (e.g., `group_64a1b2c3d4e5f`)
- Fields: `field_` followed by a unique identifier (e.g., `field_64a1b2c3d4e5f`)

Use a combination of timestamp and random characters for uniqueness.
