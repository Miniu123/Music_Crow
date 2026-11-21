package io.github.miniu123.musiccrow;

import android.content.Context;
import android.net.Uri;
import androidx.media3.database.StandaloneDatabaseProvider;
import androidx.media3.datasource.*;
import androidx.media3.datasource.cache.*;
import java.io.File;
import java.io.IOException;
import java.util.*;
import org.json.*;

@androidx.annotation.OptIn(markerClass = androidx.media3.common.util.UnstableApi.class)
final class AudioSources {
  private static AudioSources shared;

  static synchronized AudioSources get(Context context) {
    if (shared == null) shared = new AudioSources(context.getApplicationContext());
    return shared;
  }

  final SimpleCache cache;
  final CacheDataSource.Factory factory;
  private final Map<String, JSONObject> resolved = new HashMap<>();

  private AudioSources(Context context) {
    cache =
        new SimpleCache(
            new File(context.getCacheDir(), "audio"),
            new LeastRecentlyUsedCacheEvictor(200L * 1024 * 1024),
            new StandaloneDatabaseProvider(context));
    DefaultHttpDataSource.Factory http =
        new DefaultHttpDataSource.Factory().setConnectTimeoutMs(15000).setReadTimeoutMs(20000);
    ResolvingDataSource.Factory resolver =
        new ResolvingDataSource.Factory(
            new DefaultDataSource.Factory(context, http),
            spec -> {
              if (!"crow".equals(spec.uri.getScheme())) return spec;
              String page = Uri.decode(spec.uri.getEncodedSchemeSpecificPart());
              try {
                JSONObject info;
                synchronized (resolved) {
                  info = resolved.get(page);
                }
                if (info == null
                    || System.currentTimeMillis() / 1000 - info.optLong("resolved_at") > 600) {
                  info = new JSONObject(CrowApp.instance.source("resolve", page));
                  synchronized (resolved) {
                    if (resolved.size() > 30) resolved.clear();
                    resolved.put(page, info);
                  }
                }
                Map<String, String> headers = new HashMap<>();
                JSONObject values = info.optJSONObject("headers");
                if (values != null) {
                  Iterator<String> keys = values.keys();
                  while (keys.hasNext()) {
                    String key = keys.next();
                    headers.put(key, values.getString(key));
                  }
                }
                return spec.withUri(Uri.parse(info.getString("url"))).withRequestHeaders(headers);
              } catch (Exception error) {
                throw new IOException(
                    "Nie można pobrać audio ze źródła / Cannot load source audio", error);
              }
            });
    factory =
        new CacheDataSource.Factory()
            .setCache(cache)
            .setUpstreamDataSourceFactory(resolver)
            .setCacheKeyFactory(spec -> spec.key != null ? spec.key : spec.uri.toString())
            .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR);
  }

  void invalidate() {
    synchronized (resolved) {
      resolved.clear();
    }
  }
}
