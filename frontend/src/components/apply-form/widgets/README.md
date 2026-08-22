# USWDS React JSON Schema Widgets

These are based on the core widgets from [React JSON Schema](https://github.com/rjsf-team/react-jsonschema-form/tree/main/packages/core/src/components/widgets).

## Changes

They are adapted for the current project through a change in the props `UswdsWidgetProps` which makes:

- providing the `value` and `onChange` and other `on*` functions optional so the form can be submitted as a regular form instead of a JS only form
- `placeholder` is also not recommended by USWDS so is removed
- `aria-required` is substituted for `required` so the form can submit

## Nested repeating groups

`fieldList` renders an array of objects. A root-level list can continue to use
only `name`; its schema definition defaults to `/properties/<name>`.

A `fieldList` nested inside another `fieldList` must provide `definition`, the
exact JSON Schema pointer to its array. Child definitions remain absolute JSON
Schema pointers. For example:

```json
{
  "type": "fieldList",
  "name": "projects",
  "label": "Projects",
  "children": [
    {
      "type": "fieldList",
      "name": "periods",
      "label": "Budget periods",
      "definition": "/properties/projects/items/properties/periods",
      "children": [
        {
          "type": "field",
          "definition": "/properties/projects/items/properties/periods/items/properties/amount"
        }
      ]
    }
  ]
}
```

The explicit pointer lets the form engine derive cardinality, required fields,
saved-data paths, indexed validation paths, and unique input IDs at every level.
Tables and sections are not supported as `fieldList` children.
