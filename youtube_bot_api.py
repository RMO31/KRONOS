import os
import requests
import datetime
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hlknmtrnlixmctvewobw.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhsa25tdHJubGl4bWN0dmV3b2J3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEwMDUwODAsImV4cCI6MjA5NjU4MTA4MH0.22ZQTQD3ZukP7Qr2gRlCATmQmkWxC_A8dkwPuqcvbOg")
YT_API_KEY = os.environ.get("YT_API_KEY", "AIzaSyDHq4kjSuizAM6b4ttJnru0TU0QT1ZoWKM")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_channel_info(channel_id):
    """يجلب معلومات القناة: الاسم، اللوجو، وعدد المشتركين"""
    url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id={channel_id}&key={YT_API_KEY}"
    res = requests.get(url)
    if res.status_code == 200:
        items = res.json().get('items', [])
        if items:
            snippet = items[0]['snippet']
            stats = items[0]['statistics']
            return {
                'channel_name': snippet.get('title', ''),
                'channel_logo': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                'subscriber_count': int(stats.get('subscriberCount', 0))
            }
    return None

def fetch_latest_videos(channel_id):
    """يجلب آخر 5 فيديوهات للقناة"""
    playlist_id = 'UU' + channel_id[2:]
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}&maxResults=5&key={YT_API_KEY}"
    response = requests.get(url)
    
    videos = []
    if response.status_code == 200:
        data = response.json()
        for item in data.get('items', []):
            snippet = item['snippet']
            videos.append({
                'youtube_id': snippet['resourceId']['videoId'],
                'title': snippet['title'],
                'description': snippet['description'][:500] if snippet['description'] else '',
                'published_at': snippet['publishedAt'],
                'status': 'published'
            })
    return videos

def main():
    print("Starting YouTube Bot...")
    response = supabase.table('youtube_channels').select('*').execute()
    channels = response.data
    
    if not channels:
        print("No channels found.")
        return
        
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for ch in channels:
        # 1. التحقق من مرور 24 ساعة منذ آخر فحص لتوفير الموارد
        last_checked = ch.get('last_checked_at')
        if last_checked:
            # Parse ISO date safely
            try:
                last_checked_dt = datetime.datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
                if (now - last_checked_dt).total_seconds() < 86400: # 86400 seconds = 24 hours
                    print(f"Skipping {ch.get('channel_name', ch['channel_id'])} (checked less than 24h ago).")
                    continue
            except Exception as e:
                pass # If parsing fails, we fetch anyway
                
        print(f"Processing channel: {ch.get('channel_name', ch['channel_id'])}...")
        
        # 2. جلب معلومات القناة (لوجو، اسم، مشتركين)
        info = fetch_channel_info(ch['channel_id'])
        if info:
            try:
                supabase.table('youtube_channels').update({
                    'channel_name': info['channel_name'],
                    'channel_logo': info['channel_logo'],
                    'subscriber_count': info['subscriber_count'],
                    'last_info_updated_at': now.isoformat()
                }).eq('id', ch['id']).execute()
            except Exception as e:
                print("Error updating channel info:", e)
        
        # 3. جلب آخر 5 فيديوهات
        videos = fetch_latest_videos(ch['channel_id'])
        for v in videos:
            v['channel_id'] = ch['id']
            v['channel_youtube_id'] = ch['channel_id']
            v['category'] = ch.get('category', 'عام')
            
            try:
                supabase.table('videos').upsert(v, on_conflict='youtube_id').execute()
            except Exception as e:
                print(f"Error upserting video {v['youtube_id']}: {e}")
                
        # 4. تحديث وقت آخر فحص
        try:
            supabase.table('youtube_channels').update({
                'last_checked_at': now.isoformat()
            }).eq('id', ch['id']).execute()
        except Exception as e:
            print("Error updating last_checked_at", e)

    print("✅ YouTube Bot finished successfully!")

if __name__ == "__main__":
    main()
