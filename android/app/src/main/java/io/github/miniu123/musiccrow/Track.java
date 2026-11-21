package io.github.miniu123.musiccrow;

import android.net.Uri;
import android.os.Bundle;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import org.json.*;

final class Track {
  static MediaItem item(JSONObject track) {
    String url = track.optString("url");
    Uri uri = Uri.parse(url.startsWith("https://") ? "crow:" + Uri.encode(url) : url);
    Bundle extras = new Bundle();
    extras.putString("track", track.toString());
    MediaMetadata.Builder metadata =
        new MediaMetadata.Builder()
            .setTitle(track.optString("title", "Utwór"))
            .setArtist(
                track.optString("artist").isEmpty()
                    ? track.optString("uploader")
                    : track.optString("artist"))
            .setExtras(extras);
    String art = track.optString("thumbnail_url");
    if (art.startsWith("https://")) metadata.setArtworkUri(Uri.parse(art));
    return new MediaItem.Builder()
        .setMediaId(url)
        .setUri(uri)
        .setMediaMetadata(metadata.build())
        .build();
  }

  static JSONObject json(MediaItem item) {
    if (item != null && item.mediaMetadata.extras != null) {
      try {
        return new JSONObject(item.mediaMetadata.extras.getString("track", "{}"));
      } catch (Exception ignored) {
      }
    }
    return new JSONObject();
  }

  static String artist(JSONObject t) {
    return t.optString("artist").isEmpty() ? t.optString("uploader") : t.optString("artist");
  }
}
