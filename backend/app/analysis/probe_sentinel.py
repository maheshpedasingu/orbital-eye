from app.aoi import aoi_bbox
from app.ingestion.stac import list_collections, search_items, summarize_item

if __name__ == "__main__":
    bbox = aoi_bbox(0.0)
    print("AOI bbox (west, south, east, north):", bbox)

    cols = [
        c for c in list_collections()
        if "sentinel-2" in (c["id"] or "") and "l2a" in (c["id"] or "")
    ]
    print("\nSentinel-2 L2A collections:")
    for c in cols:
        print(" ", c["id"], c["interval"])

    for c in cols:
        items = search_items(c["id"], bbox, days=45)
        print(f"\n[{c['id']}] {len(items)} item(s) in the last 45 days")
        summaries = [summarize_item(i) for i in items]
        summaries.sort(key=lambda s: s["datetime"] or "", reverse=True)
        for s in summaries[:5]:
            print(" ", s["id"], s["datetime"], "cloud", s["cloud_cover"], s["platform"])
        if summaries:
            first = summaries[0]
            print("  asset keys:", first["asset_keys"])
            for key, info in first["bands"].items():
                print("  ", key, info)
