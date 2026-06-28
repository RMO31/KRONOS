import os
import requests
import datetime
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hlknmtrnlixmctvewobw.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhsa25tdHJubGl4bWN0dmV3b2J3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEwMDUwODAsImV4cCI6MjA5NjU4MTA4MH0.22ZQTQD3ZukP7Qr2gRlCATmQmkWxC_A8dkwPuqcvbOg")
YT_API_KEY   = os.environ.get("YT_API_KEY",   "AIzaSyDHq4kjSuizAM6b4ttJnru0TU0QT1ZoWKM")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_channel_info(channel_id):
    """يجلب معلومات القناة: الاسم، اللوجو، وعدد المشتركين"""
    url = (f"https://www.googleapis.com/youtube/v3/channels"
           f"?part=snippet,statistics&id={channel_id}&key={YT_API_KEY}")
    res = requests.get(url, timeout=15)
    if res.status_code == 200:
        items = res.json().get('items', [])
        if items:
            snippet = items[0]['snippet']
            stats   = items[0]['statistics']
            return {
                'channel_name':    snippet.get('title', ''),
                'channel_logo':    snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                'subscriber_count': int(stats.get('subscriberCount', 0))
            }
    print(f"  ⚠️  fetch_channel_info HTTP {res.status_code}")
    return None

def fetch_latest_videos(channel_id, max_results=10):
    """يجلب آخر فيديوهات للقناة (افتراضي 10)"""
    playlist_id = 'UU' + channel_id[2:]   # UC… → UU…
    url = (f"https://www.googleapis.com/youtube/v3/playlistItems"
           f"?part=snippet&playlistId={playlist_id}&maxResults={max_results}&key={YT_API_KEY}")
    res = requests.get(url, timeout=15)
    videos = []
    if res.status_code == 200:
        data = res.json()
        if data.get('error'):
            print(f"  ⚠️  YT API error: {data['error'].get('message')}")
            return videos
        for item in data.get('items', []):
            snippet = item.get('snippet', {})
            vid_id  = snippet.get('resourceId', {}).get('videoId')
            if not vid_id:
                continue
            videos.append({
                'youtube_id':   vid_id,
                'title':        snippet.get('title', ''),
                'description':  (snippet.get('description', '') or '')[:500],
                'published_at': snippet.get('publishedAt'),
                'status':       'published'
            })
    else:
        print(f"  ⚠️  fetch_latest_videos HTTP {res.status_code}: {res.text[:200]}")
    return videos

def save_video(video_body):
    """
    يحاول INSERT أولاً — إذا كان الفيديو موجوداً (كود 23505)
    ينتقل إلى UPDATE لتحديث بيانات القناة والتصنيف.
    """
    vid = video_body['youtube_id']
    try:
        supabase.table('videos').insert(video_body).execute()
        return 'inserted'
    except Exception as e:
        err_str = str(e)
        if '23505' in err_str or 'duplicate' in err_str.lower():
            # الفيديو موجود بالفعل → حدّث القناة والتصنيف فقط
            try:
                supabase.table('videos').update({
                    'channel_id':         video_body.get('channel_id'),
                    'channel_youtube_id': video_body.get('channel_youtube_id'),
                    'category':           video_body.get('category'),
                }).eq('youtube_id', vid).execute()
                return 'updated'
            except Exception as e2:
                print(f"    ❌ update failed for {vid}: {e2}")
                return 'error'
        else:
            print(f"    ❌ insert failed for {vid}: {e}")
            return 'error'

def main():
    print("=" * 50)
    print("🤖 Starting YouTube Bot...")
    print("=" * 50)

    response = supabase.table('youtube_channels').select('*').execute()
    channels = response.data or []

    if not channels:
        print("⚠️  No channels found in DB.")
        return

    now = datetime.datetime.now(datetime.timezone.utc)

    for ch in channels:
        ch_name = ch.get('channel_name') or ch['channel_id']
        print(f"\n📺 Channel: {ch_name}  [{ch['channel_id']}]")

        # ── 1. تجاوز إذا تم الفحص منذ أقل من 24 ساعة ─────────────────────
        last_checked = ch.get('last_checked_at')
        if last_checked:
            try:
                last_dt = datetime.datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
                diff_h  = (now - last_dt).total_seconds() / 3600
                if diff_h < 24:
                    print(f"  ⏭  Skipped (checked {diff_h:.1f}h ago)")
                    continue
            except Exception:
                pass

        # ── 2. تحديث معلومات القناة ──────────────────────────────────────
        info = fetch_channel_info(ch['channel_id'])
        if info:
            try:
                supabase.table('youtube_channels').update({
                    'channel_name':       info['channel_name'],
                    'channel_logo':       info['channel_logo'],
                    'subscriber_count':   info['subscriber_count'],
                    'last_info_updated_at': now.isoformat()
                }).eq('id', ch['id']).execute()
                print(f"  ✅ Channel info updated: {info['channel_name']}")
            except Exception as e:
                print(f"  ❌ Error updating channel info: {e}")

        # ── 3. جلب وحفظ آخر الفيديوهات ────────────────────────────────────
        videos = fetch_latest_videos(ch['channel_id'], max_results=10)
        print(f"  📥 Fetched {len(videos)} videos from YouTube")

        inserted = updated = errors = 0
        for v in videos:
            v['channel_id']         = ch['id']
            v['channel_youtube_id'] = ch['channel_id']
            v['category']           = ch.get('category', 'عام')

            result = save_video(v)
            if result == 'inserted': inserted += 1
            elif result == 'updated': updated += 1
            else: errors += 1

        print(f"  💾 inserted={inserted}  updated={updated}  errors={errors}")

        # ── 4. تحديث وقت آخر فحص ──────────────────────────────────────────
        try:
            supabase.table('youtube_channels').update({
                'last_checked_at': now.isoformat()
            }).eq('id', ch['id']).execute()
        except Exception as e:
            print(f"  ❌ Error updating last_checked_at: {e}")

    print("\n" + "=" * 50)
    print("✅ YouTube Bot finished successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()
