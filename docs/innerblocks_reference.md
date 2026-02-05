# InnerBlocks in ACF PHP Templates

InnerBlocks allow your ACF block to contain other Gutenberg blocks inside it. This is useful for container blocks, sections, columns, etc.

## Enabling InnerBlocks

In your block.json, set `jsx: true` in supports:

```json
{
    "name": "acf/container-block",
    "title": "Container Block",
    "supports": {
        "jsx": true
    }
}
```

## Basic PHP Template with InnerBlocks

```php
<?php
/**
 * Block Name: Container Block
 * Description: A container that holds other blocks
 */

$block_id = 'block-' . $block['id'];
$block_classes = 'acf-block container-block';
if (!empty($block['className'])) {
    $block_classes .= ' ' . $block['className'];
}

// Get ACF fields
$background_color = get_field('background_color');
?>

<div id="<?php echo esc_attr($block_id); ?>" class="<?php echo esc_attr($block_classes); ?>"
    <?php if ($background_color) : ?>
        style="background-color: <?php echo esc_attr($background_color); ?>;"
    <?php endif; ?>>

    <div class="container-block__inner">
        <?php echo $block['innerBlocksHtml']; ?>
    </div>

</div>
```

## Using allowedBlocks to Restrict Inner Content

You can limit which blocks are allowed inside your container:

```php
<?php
$allowed_blocks = array(
    'core/heading',
    'core/paragraph',
    'core/image',
    'core/list',
);

$template = array(
    array('core/heading', array('placeholder' => 'Add a heading...')),
    array('core/paragraph', array('placeholder' => 'Add content...')),
);
?>

<div class="<?php echo esc_attr($block_classes); ?>">
    <InnerBlocks
        allowedBlocks="<?php echo esc_attr(wp_json_encode($allowed_blocks)); ?>"
        template="<?php echo esc_attr(wp_json_encode($template)); ?>"
    />
</div>
```

## InnerBlocks with Template Lock

Prevent users from adding/removing/moving blocks:

```php
<?php
$template = array(
    array('core/heading', array('level' => 2)),
    array('core/paragraph'),
    array('core/button'),
);
?>

<div class="<?php echo esc_attr($block_classes); ?>">
    <InnerBlocks
        template="<?php echo esc_attr(wp_json_encode($template)); ?>"
        templateLock="all"
    />
</div>
```

Template lock options:
- `"all"` - Blocks cannot be added, removed, or moved
- `"insert"` - Blocks cannot be added or removed, but can be moved
- `false` - No locking (default)

## Rendering InnerBlocks on Frontend vs Editor

The `$block['innerBlocksHtml']` variable contains:
- **In Editor**: The `<InnerBlocks />` React component
- **On Frontend**: The rendered HTML of all inner blocks

```php
<?php
// This works for both editor preview and frontend
$inner_content = $block['innerBlocksHtml'];

// Check if we have inner content
$has_inner_blocks = !empty(trim(strip_tags($inner_content)));
?>

<section class="<?php echo esc_attr($block_classes); ?>">
    <?php if ($has_inner_blocks) : ?>
        <div class="section__content">
            <?php echo $inner_content; ?>
        </div>
    <?php else : ?>
        <p class="section__placeholder">Add blocks here...</p>
    <?php endif; ?>
</section>
```

## Two-Column Layout Example

```php
<?php
$block_id = 'block-' . $block['id'];
$block_classes = 'acf-block two-column-block';

$left_column_width = get_field('left_column_width') ?: '50';
?>

<div id="<?php echo esc_attr($block_id); ?>" class="<?php echo esc_attr($block_classes); ?>">
    <div class="two-column-block__left" style="flex-basis: <?php echo esc_attr($left_column_width); ?>%;">
        <?php
        // First InnerBlocks area
        $template_left = array(array('core/paragraph'));
        ?>
        <InnerBlocks
            allowedBlocks="<?php echo esc_attr(wp_json_encode(array('core/heading', 'core/paragraph', 'core/image'))); ?>"
            template="<?php echo esc_attr(wp_json_encode($template_left)); ?>"
        />
    </div>
    <div class="two-column-block__right" style="flex-basis: <?php echo esc_attr(100 - intval($left_column_width)); ?>%;">
        <!-- Note: ACF blocks can only have ONE InnerBlocks area -->
        <!-- For multiple areas, use nested ACF blocks or core/columns -->
    </div>
</div>
```

**Important**: Each ACF block can only contain ONE `<InnerBlocks />` area. For multiple editable regions, consider using nested blocks or the core columns block.

## Block Registration with InnerBlocks (block.json)

```json
{
    "name": "acf/container-section",
    "title": "Container Section",
    "description": "A section that can contain other blocks",
    "category": "theme",
    "icon": "layout",
    "keywords": ["container", "section", "wrapper"],
    "acf": {
        "mode": "preview",
        "renderTemplate": "blocks/container-section/container-section.php"
    },
    "supports": {
        "align": ["wide", "full"],
        "anchor": true,
        "customClassName": true,
        "jsx": true
    }
}
```
