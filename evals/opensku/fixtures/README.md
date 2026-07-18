# OpenSKU Fixture Notes

The Phase 2 benchmark cases reference Phase 1 sample files directly instead of copying raw rows here.

Current referenced sample files:

```text
data/opensku/samples/amazon_reviews.jsonl
data/opensku/samples/olist.jsonl
data/opensku/samples/wands.jsonl
```

Each JSONL line has this shape:

```json
{
  "dataset": "wands",
  "component": "query",
  "row": {}
}
```

Large raw public datasets should not be committed here. Add only small, attributed fixtures that are required for deterministic case validation.

