import os
import sys
import argparse
import json
from datetime import datetime, timedelta, timezone

# pip install gpxpy python-dateutil requests
import gpxpy
import gpxpy.gpx
from dateutil import parser
import requests

api_key = "YOUR_API_KEY"

cache_file = "place_cache.json"
place_cache = {}

# 統計用
stats = {
    "timelinePath": 0,
    "activity": 0,
    "visit": 0,
    "interpolated": 0,
    "skipped": 0,
    "cache_hit": 0,
    "api_query": 0
}

# 嘗試載入快取
if os.path.exists(cache_file):
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            place_cache = json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load cache: {e}")

# 命令列參數
arg_parser = argparse.ArgumentParser(description="Convert location history to GPX")
arg_parser.add_argument("-d", "--date", help="Target date in YYYY-MM-DD format")
arg_parser.add_argument("-r", "--range", help="Date range in format YYYY-MM-DD:YYYY-MM-DD (inclusive)")
arg_parser.add_argument("-i", "--input", default="location-history.json", help="Path to location history JSON file")
arg_parser.add_argument("-t", "--timezone", type=int, default=8, help="Timezone offset in hours from UTC")
arg_parser.add_argument("-nc", "--nocache", action="store_true", help="Disable place name cache")
arg_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed processing output")
args = arg_parser.parse_args()

# 檢查至少有 --date 或 --range
if not args.date and not args.range:
    arg_parser.error("You must specify either --date or --range.")

# 時區設定
tz_target = timezone(timedelta(hours=args.timezone))

# 日期處理
if args.range:
    try:
        start_str, end_str = args.range.split(":")
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        date_list = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    except Exception as e:
        print(f"❌ Invalid date range format: {e}")
        sys.exit(1)
elif args.date:
    date_list = [datetime.strptime(args.date, "%Y-%m-%d").date()]
else:
    print("❌ Please specify either --date or --range")
    sys.exit(1)

# 載入 JSON 資料
try:
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print(f"❌ Failed to load input file: {e}")
    sys.exit(1)

# 排序資料
data.sort(key=lambda x: parser.isoparse(x["startTime"]))

# 工具函式
def parse_geo(geo_str):
    lat, lon = geo_str.replace("geo:", "").split(",")
    return float(lat), float(lon)

def parse_time(t):
    dt = parser.isoparse(t)
    return dt.astimezone(tz_target)

def to_gpx_time(dt):
    return dt.astimezone(timezone.utc)

def get_place_name_from_api(place_id):
    if not args.nocache and place_id in place_cache:
        stats["cache_hit"] += 1
        return place_cache[place_id]
    else:
        stats["api_query"] += 1

    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&language=zh-TW&key={api_key}"
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "OK":
            name = data["result"]["name"]
            place_cache[place_id] = name
            return name
        else:
            if args.verbose:
                print(f"⚠️ Google API returned status: {data.get('status')}")
    except Exception as e:
        if args.verbose:
            print(f"⚠️ Failed to fetch place name: {e}")
    return None

def has_path_between(start, end, entries):
    for e in entries:
        if "activity" not in e and "timelinePath" not in e:
            continue

        t_start = parse_time(e["startTime"])
        t_end = parse_time(e["endTime"])
        if t_end > start and t_start < end:
            if "activity" in e or "timelinePath" in e:
                return True
    return False

def format_range_desc(start_dt, end_dt):
    start_local = start_dt.astimezone(tz_target)
    end_local = end_dt.astimezone(tz_target)
    duration = end_local - start_local
    minutes = int(duration.total_seconds() // 60)
    return f"from {start_local.isoformat()} to {end_local.isoformat()} ({minutes} min)"

# 主處理函式
def process_date(target_date_str, data):
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "Location History Converter"
    gpx.name = f"Location History for {target_date_str}"
    gpx.description = "Generated from location history JSON"
    gpx.author_name = "Cloud Ho"

    previous_visit = None
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    for i, entry in enumerate(data):
        try:
            start_time = parse_time(entry["startTime"])
            end_time = parse_time(entry["endTime"])
        except Exception as e:
            if args.verbose:
                print(f"⚠️ Skipping entry {i} due to time parsing error: {e}")
            stats["skipped"] += 1
            continue

        if start_time.date() != target_date:
            stats["skipped"] += 1
            continue

        # 匯出 timelinePath
        if "timelinePath" in entry:
            segment = gpxpy.gpx.GPXTrackSegment()
            for point in entry["timelinePath"]:
                lat, lon = parse_geo(point["point"])
                offset_min = int(float(point["durationMinutesOffsetFromStartTime"]))
                time = start_time + timedelta(minutes=offset_min)
                segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon, time=to_gpx_time(time)))
            track = gpxpy.gpx.GPXTrack()
            track.name = "Timeline Path"
            track.description = format_range_desc(start_time, end_time)
            track.segments.append(segment)
            gpx.tracks.append(track)
            stats["timelinePath"] += 1
            if args.verbose:
                print(f"✅ TimelinePath added from {start_time}")

        # 匯出 activity
        elif "activity" in entry:
            lat1, lon1 = parse_geo(entry["activity"]["start"])
            lat2, lon2 = parse_geo(entry["activity"]["end"])
            segment = gpxpy.gpx.GPXTrackSegment()
            segment.points.append(gpxpy.gpx.GPXTrackPoint(lat1, lon1, time=to_gpx_time(start_time)))
            segment.points.append(gpxpy.gpx.GPXTrackPoint(lat2, lon2, time=to_gpx_time(end_time)))
            track = gpxpy.gpx.GPXTrack()
            track.name = entry["activity"]["topCandidate"]["type"]
            track.description = format_range_desc(start_time, end_time)
            track.segments.append(segment)
            gpx.tracks.append(track)
            stats["activity"] += 1
            if args.verbose:
                print(f"✅ Activity added: {track.name} from {start_time}")

        # 匯出 visit
        elif "visit" in entry:
            lat, lon = parse_geo(entry["visit"]["topCandidate"]["placeLocation"])
            wpt = gpxpy.gpx.GPXWaypoint(latitude=lat, longitude=lon, time=to_gpx_time(start_time))
            # 先嘗試取得原始名稱
            original_name = entry["visit"]["topCandidate"].get("semanticType", "").strip()

            # 如果名稱是空的或 Unknown，就嘗試查詢 placeID
            if not original_name or original_name.lower() == "unknown":
                place_id = entry["visit"]["topCandidate"].get("placeID")
                if place_id:
                    place_name = get_place_name_from_api(place_id)
                    wpt.name = place_name if place_name else "Unknown Place"
                else:
                    wpt.name = "Unknown Place"
            else:
                wpt.name = original_name

            start_dt = parse_time(entry["startTime"])
            end_dt = parse_time(entry["endTime"])
            wpt.description = format_range_desc(start_time, end_time)
            gpx.waypoints.append(wpt)
            stats["visit"] += 1
            if args.verbose:
                print(f"✅ Visit added: {wpt.name} at {start_time}")

            # 檢查是否需要補直線
            if previous_visit:
                if not has_path_between(previous_visit["time"], start_time, data):
                    segment = gpxpy.gpx.GPXTrackSegment()
                    segment.points.append(gpxpy.gpx.GPXTrackPoint(previous_visit["lat"], previous_visit["lon"], time=to_gpx_time(previous_visit["time"])))
                    segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon, time=to_gpx_time(start_time)))
                    track = gpxpy.gpx.GPXTrack()
                    track.name = "Interpolated Visit Path"
                    track.segments.append(segment)
                    gpx.tracks.append(track)
                    stats["interpolated"] += 1
                    if args.verbose:
                        print(f"🔄 Interpolated path added between visits")

            previous_visit = {"lat": lat, "lon": lon, "time": start_time}

    # 寫入 GPX 檔案
    output_file = f"gpx_{target_date_str}.gpx"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(gpx.to_xml())
        print(f"\n✅ GPX file saved: {output_file}")
    except Exception as e:
        print(f"❌ Failed to write GPX file: {e}")

for target_date in date_list:
    if args.verbose:
        print(f"\n📅 Processing {target_date}...")
    process_date(target_date.isoformat(), data)

# 保存place快取
try:
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(place_cache, f, ensure_ascii=False, indent=2)
    if args.verbose:
        print(f"💾 Cache saved to {cache_file}")
except Exception as e:
    print(f"⚠️ Failed to save cache: {e}")

# 顯示統計摘要
print("\n📊 Summary:")
print(f"  Timeline Paths:  {stats['timelinePath']}")
print(f"  Activities:      {stats['activity']}")
print(f"  Visits:          {stats['visit']}")
print(f"  Interpolations:  {stats['interpolated']}")
print(f"  Skipped:         {stats['skipped']}")
print(f"  Cache Hits:      {stats['cache_hit']}")
print(f"  API Queries:     {stats['api_query']}")