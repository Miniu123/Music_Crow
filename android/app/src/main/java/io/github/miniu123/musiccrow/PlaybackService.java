package io.github.miniu123.musiccrow;

import android.app.PendingIntent;
import android.content.*;
import android.media.audiofx.Equalizer;
import android.os.*;
import androidx.media3.common.*;
import androidx.media3.datasource.DataSpec;
import androidx.media3.datasource.cache.CacheWriter;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.session.*;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

@androidx.annotation.OptIn(markerClass = androidx.media3.common.util.UnstableApi.class)
public final class PlaybackService extends MediaSessionService {
  public static PlaybackService active;
  public static volatile List<JSONObject> recommendations = Collections.emptyList();
  public static volatile String preparation = "";
  public static volatile String playbackError = "";
  public static volatile boolean recommendationLoading, recommendationFailed;
  private MediaSession session;
  private ExoPlayer player;
  private ExoPlayer tail;
  private AudioSources sources;
  private Equalizer equalizer;
  private Equalizer tailEqualizer;
  private int eqSession = C.AUDIO_SESSION_ID_UNSET, tailEqSession = C.AUDIO_SESSION_ID_UNSET;
  private int rotation = (int) (System.currentTimeMillis() / 86400000);
  private final Handler handler = new Handler(Looper.getMainLooper());
  private final ExecutorService prefetchExecutor = Executors.newSingleThreadExecutor();
  private CacheWriter prefetch;
  private String prefetchId = "";
  private long lastTick, heard, fadeStart;
  private boolean recorded, wasPlaying, stopped, fading, tailPreparing;
  private boolean awaitingRecommendation, continuingQueue;
  private volatile boolean destroyed;
  private String readyId = "";
  private volatile int recommendationGeneration;
  private int fadeLength;
  private int tailGeneration;
  private final Set<String> consumed = new HashSet<>();
  private long lastDiscovery;
  private String discoveryContext = "";
  private String recommendationRequestKey = "";
  private List<JSONObject> discoveryCache = new ArrayList<>();
  private final Runnable tick =
      new Runnable() {
        @Override
        public void run() {
          if (destroyed) return;
          long now = SystemClock.elapsedRealtime();
          if (player.isPlaying() && wasPlaying && !recorded) {
            heard += Math.max(0, Math.min(1500, now - lastTick));
            long length = player.getDuration();
            long threshold = length > 0 ? Math.min(30000, Math.max(5000, length / 2)) : 30000;
            if (heard >= threshold) {
              recorded = true;
              JSONObject track = Track.json(player.getCurrentMediaItem());
              CrowApp.IO.execute(
                  () -> {
                    try {
                      CrowApp.instance.call("record", CrowApp.obj("track", track));
                    } catch (Exception ignored) {
                    }
                  });
            }
          }
          lastTick = now;
          wasPlaying = player.isPlaying();
          updateFade(now);
          handler.postDelayed(this, 250);
        }
      };
  private final BroadcastReceiver settingsChanged =
      new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
          applyEqualizer();
          prepareNext();
        }
      };

  @Override
  public void onCreate() {
    super.onCreate();
    active = this;
    sources = AudioSources.get(this);
    player =
        new ExoPlayer.Builder(this)
            .setMediaSourceFactory(new DefaultMediaSourceFactory(sources.factory))
            .build();
    player.setAudioAttributes(
        new AudioAttributes.Builder()
            .setUsage(C.USAGE_MEDIA)
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .build(),
        true);
    player.setHandleAudioBecomingNoisy(true);
    player.setWakeMode(C.WAKE_MODE_LOCAL);
    tail =
        new ExoPlayer.Builder(this)
            .setMediaSourceFactory(new DefaultMediaSourceFactory(sources.factory))
            .build();
    tail.setAudioAttributes(
        new AudioAttributes.Builder()
            .setUsage(C.USAGE_MEDIA)
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .build(),
        false);
    player.addListener(
        new Player.Listener() {
          @Override
          public void onMediaItemTransition(MediaItem item, int reason) {
            awaitingRecommendation = false;
            heard = 0;
            recorded = false;
            wasPlaying = false;
            if (item != null) consumed.add(item.mediaId);
            if (consumed.size() > 500) consumed.clear();
            playbackError = "";
            prepareNext();
            refreshRecommendations(false);
          }

          @Override
          public void onTimelineChanged(Timeline timeline, int reason) {
            prepareNext();
          }

          @Override
          public void onShuffleModeEnabledChanged(boolean enabled) {
            prepareNext();
          }

          @Override
          public void onRepeatModeChanged(int mode) {
            cancelFade();
            prepareNext();
          }

          @Override
          public void onPositionDiscontinuity(
              Player.PositionInfo oldPosition, Player.PositionInfo newPosition, int reason) {
            if (reason == Player.DISCONTINUITY_REASON_SEEK && !fading) cancelFade();
          }

          @Override
          public void onIsPlayingChanged(boolean playing) {
            if (!playing && !fading && !tailPreparing) tail.pause();
          }

          @Override
          public void onPlayWhenReadyChanged(boolean playing, int reason) {
            if (!playing) {
              awaitingRecommendation = false;
              cancelFade();
            } else continueQueue();
          }

          @Override
          public void onPlaybackStateChanged(int state) {
            if (state == Player.STATE_ENDED) continueQueue();
          }

          @Override
          public void onAudioSessionIdChanged(int id) {
            applyEqualizer();
          }

          @Override
          public void onPlayerError(PlaybackException error) {
            awaitingRecommendation = false;
            sources.invalidate();
            cancelFade();
            playbackError =
                "Nie można odtworzyć. Spróbuj ponownie lub wybierz inny utwór. / Playback failed."
                    + " Retry or choose another track.";
          }
        });
    tail.addListener(
        new Player.Listener() {
          @Override
          public void onAudioSessionIdChanged(int id) {
            applyEqualizer();
          }

          @Override
          public void onPlayerError(PlaybackException error) {
            cancelFade();
          }
        });
    PendingIntent launch =
        PendingIntent.getActivity(
            this,
            0,
            new Intent(this, MainActivity.class),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    // Keep Next available at the end of the timeline, including system/Bluetooth controls.
    Player sessionPlayer =
        new ForwardingSimpleBasePlayer(player) {
          @Override
          protected State getState() {
            State state = super.getState();
            Player.Commands.Builder commands = player.getAvailableCommands().buildUpon();
            if (player.getCurrentMediaItem() != null)
              commands.add(Player.COMMAND_SEEK_TO_NEXT).add(Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM);
            return state.buildUpon().setAvailableCommands(commands.build()).build();
          }

          @Override
          protected ListenableFuture<?> handleSeek(int index, long positionMs, int command) {
            if (command == Player.COMMAND_SEEK_TO_NEXT
                || command == Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM) {
              nextTrack();
              return Futures.immediateVoidFuture();
            }
            editQueue();
            return super.handleSeek(index, positionMs, command);
          }

          @Override
          protected ListenableFuture<?> handleStop() {
            stopPlayback();
            return Futures.immediateVoidFuture();
          }
        };
    session = new MediaSession.Builder(this, sessionPlayer).setSessionActivity(launch).build();
    androidx.core.content.ContextCompat.registerReceiver(
        this,
        settingsChanged,
        new IntentFilter(CrowApp.CHANGED),
        androidx.core.content.ContextCompat.RECEIVER_NOT_EXPORTED);
    lastTick = SystemClock.elapsedRealtime();
    handler.post(tick);
  }

  public void startSession() {
    stopped = false;
    awaitingRecommendation = false;
    consumed.clear();
    cancelFade();
    recommendations = Collections.emptyList();
    recommendationLoading = false;
    recommendationFailed = false;
    recommendationGeneration++;
    discoveryCache.clear();
    discoveryContext = "";
    lastDiscovery = 0;
  }

  public void stopPlayback() {
    stopped = true;
    awaitingRecommendation = false;
    cancelFade();
    // stop() alone keeps playWhenReady, so a later "next" would start playing on its own.
    // Like a pause, a stop must survive skipping; Play (or choosing a track) resumes playback.
    player.setPlayWhenReady(false);
    player.stop();
    prepareNext();
  }

  public void editQueue() {
    cancelFade();
    stopped = false;
    awaitingRecommendation = false;
  }

  private void nextTrack() {
    if (destroyed || player.getCurrentMediaItem() == null) return;
    cancelFade();
    stopped = false;
    if (player.hasNextMediaItem()) {
      awaitingRecommendation = false;
      player.seekToNextMediaItem();
      return;
    }
    if (awaitingRecommendation) return;
    awaitingRecommendation = true;
    continueQueue();
    // The request survives an empty first batch and is fulfilled by later discoveries.
    if (awaitingRecommendation) refreshRecommendations(false);
  }

  private void prepareNext() {
    if (sources == null || destroyed) return;
    MediaItem item = null;
    int next = player.getNextMediaItemIndex();
    boolean enabled = CrowApp.instance.settings().optBoolean("PREFETCH_ENABLED", true);
    if (enabled && !stopped && player.getCurrentMediaItem() != null) {
      if (next != C.INDEX_UNSET) item = player.getMediaItemAt(next);
      else if (player.getRepeatMode() == Player.REPEAT_MODE_OFF) {
        for (JSONObject candidate : recommendations) {
          if (eligibleRecommendation(candidate)) {
            item = Track.item(candidate);
            break;
          }
        }
      }
    }
    String id = item == null ? "" : item.mediaId;
    if (id.equals(prefetchId)) return;
    prefetchId = id;
    readyId = "";
    if (prefetch != null) prefetch.cancel();
    prefetch = null;
    preparation = "";
    if (item == null || item.localConfiguration == null) return;
    if (!"crow".equals(item.localConfiguration.uri.getScheme())) {
      readyId = id;
      preparation = "ready";
      return;
    }
    JSONObject track = Track.json(item);
    if (track.optDouble("duration") > 1200) return;
    String expected = id;
    CacheWriter writer =
        new CacheWriter(
            sources.factory.createDataSource(),
            new DataSpec.Builder()
                .setUri(item.localConfiguration.uri)
                .setLength(80L * 1024 * 1024)
                .build(),
            null,
            null);
    prefetch = writer;
    preparation = "loading";
    prefetchExecutor.execute(
        () -> {
          boolean ok = true;
          try {
            writer.cache();
          } catch (Exception e) {
            ok = false;
          }
          final boolean ready = ok;
          handler.post(
              () -> {
                if (!destroyed && writer == prefetch && expected.equals(prefetchId)) {
                  readyId = ready ? expected : "";
                  preparation = ready ? "ready" : "stream";
                }
              });
        });
  }

  private boolean eligibleRecommendation(JSONObject track) {
    if (track == null) return false;
    String id = track.optString("url");
    if (id.isEmpty() || consumed.contains(id)) return false;
    for (int i = 0; i < player.getMediaItemCount(); i++)
      if (id.equals(player.getMediaItemAt(i).mediaId)) return false;
    return true;
  }

  public void removeRecommendation(JSONObject track) {
    consumed.add(track.optString("url"));
    List<JSONObject> remaining = new ArrayList<>();
    for (JSONObject candidate : recommendations)
      if (eligibleRecommendation(candidate)) remaining.add(candidate);
    recommendations = remaining;
    // Do not cancel the discovery worker: later batches are filtered against live exclusions.
    prepareNext();
  }

  /** Moves a suggestion within the list that continues playback after the queue. */
  public void moveRecommendation(String url, int to) {
    List<JSONObject> list = new ArrayList<>(recommendations);
    int from = -1;
    for (int i = 0; i < list.size(); i++)
      if (url.equals(list.get(i).optString("url"))) {
        from = i;
        break;
      }
    if (from < 0) return;
    JSONObject track = list.remove(from);
    list.add(Math.max(0, Math.min(to, list.size())), track);
    recommendations = list;
    prepareNext();
  }

  public void refreshRecommendations(boolean force) {
    if (destroyed) return;
    String contextKey =
        player.getCurrentMediaItem() == null ? "" : player.getCurrentMediaItem().mediaId;
    if (!force && recommendationLoading && contextKey.equals(recommendationRequestKey)) return;
    if (force) rotation++;
    int generation = ++recommendationGeneration;
    recommendationRequestKey = contextKey;
    recommendationLoading = true;
    recommendationFailed = false;
    JSONArray context = new JSONArray();
    if (player.getCurrentMediaItem() != null) context.put(Track.json(player.getCurrentMediaItem()));
    JSONArray excluded = new JSONArray();
    for (int i = 0; i < player.getMediaItemCount(); i++)
      excluded.put(Track.json(player.getMediaItemAt(i)));
    for (String id : consumed) excluded.put(CrowApp.obj("url", id));
    // Re-rank cached candidates even after a track change. The ranker validates the new context.
    List<JSONObject> initialCache = new ArrayList<>(discoveryCache);
    JSONObject args =
        CrowApp.obj(
            "context",
            context,
            "excluded",
            excluded,
            "rotation",
            rotation,
            "discoveries",
            new JSONArray(initialCache));
    boolean changed = !contextKey.equals(discoveryContext);
    boolean discover =
        force
            || changed
            || SystemClock.elapsedRealtime() - lastDiscovery > 1800000
            || initialCache.isEmpty();
    discoveryContext = contextKey;
    if (changed) recommendations = Collections.emptyList();
    prepareNext();
    String platform =
        context.length() > 0
            ? context.optJSONObject(context.length() - 1).optString("platform", "YouTube Music")
            : "YouTube Music";
    CrowApp.IO.execute(
        () -> {
          List<JSONObject> cached = new ArrayList<>(initialCache);
          try {
            if (destroyed || generation != recommendationGeneration) return;
            JSONObject result = new JSONObject(CrowApp.instance.call("recommend", args));
            publishRecommendations(result, generation, cached, false, false, false);
            boolean searched = false, failed = false;
            if (discover) {
              JSONArray seeds = result.optJSONArray("seeds");
              boolean allowRemixes = result.optBoolean("allow_remixes");
              for (int i = 0; seeds != null && i < Math.min(4, seeds.length()); i++) {
                if (destroyed || generation != recommendationGeneration) return;
                try {
                  JSONObject found =
                      new JSONObject(
                          CrowApp.instance.source(
                              "discover",
                              seeds.getString(i),
                              platform.equals("SoundCloud") ? "SoundCloud" : "YouTube Music",
                              allowRemixes));
                  JSONArray tracks = found.getJSONArray("tracks");
                  for (int j = 0; j < tracks.length(); j++) cached.add(tracks.getJSONObject(j));
                  cached = boundedDiscoveries(cached);
                  searched = true;
                  args.put("discoveries", new JSONArray(cached));
                  result = new JSONObject(CrowApp.instance.call("recommend", args));
                  publishRecommendations(result, generation, cached, false, false, false);
                } catch (Exception ignored) {
                  failed = true;
                }
              }
            }
            publishRecommendations(result, generation, cached, true, failed && !searched, searched);
          } catch (Exception ignored) {
            publishRecommendations(null, generation, null, true, true, false);
          }
        });
  }

  private List<JSONObject> boundedDiscoveries(List<JSONObject> candidates) {
    LinkedHashMap<String, JSONObject> unique = new LinkedHashMap<>();
    for (JSONObject track : candidates) {
      String id = track.optString("url");
      if (id.isEmpty()) continue;
      unique.remove(id);
      unique.put(id, track);
      if (unique.size() > 240) unique.remove(unique.keySet().iterator().next());
    }
    return new ArrayList<>(unique.values());
  }

  private void publishRecommendations(JSONObject result, int generation) {
    publishRecommendations(result, generation, null, true, false, false);
  }

  private void publishRecommendations(
      JSONObject result,
      int generation,
      List<JSONObject> cache,
      boolean finished,
      boolean failed,
      boolean searched) {
    List<JSONObject> cacheSnapshot = cache == null ? null : new ArrayList<>(cache);
    handler.post(
        () -> {
          if (destroyed || generation != recommendationGeneration) return;
          if (cacheSnapshot != null) discoveryCache = cacheSnapshot;
          if (finished) {
            recommendationLoading = false;
            recommendationFailed = failed;
            if (searched) lastDiscovery = SystemClock.elapsedRealtime();
          }
          if (result != null) {
            JSONArray list = result.optJSONArray("tracks");
            List<JSONObject> ready = new ArrayList<>();
            Set<String> seen = new HashSet<>();
            for (int i = 0; list != null && i < list.length(); i++) {
              JSONObject track = list.optJSONObject(i);
              if (eligibleRecommendation(track) && seen.add(track.optString("url")))
                ready.add(track);
            }
            recommendations = ready;
          }
          continueQueue();
          prepareNext();
        });
  }

  private void continueQueue() {
    if (stopped
        || destroyed
        || continuingQueue
        || player.getCurrentMediaItem() == null
        || player.hasNextMediaItem()
        || (!awaitingRecommendation
            && (!player.getPlayWhenReady()
                || player.getPlaybackState() != Player.STATE_ENDED
                || player.getRepeatMode() != Player.REPEAT_MODE_OFF))
        || recommendations.isEmpty()) return;
    Set<String> queued = new HashSet<>(consumed);
    for (int i = 0; i < player.getMediaItemCount(); i++)
      queued.add(player.getMediaItemAt(i).mediaId);
    List<JSONObject> remaining = new ArrayList<>(recommendations);
    JSONObject next = null;
    while (!remaining.isEmpty()) {
      JSONObject candidate = remaining.remove(0);
      if (candidate != null
          && !candidate.optString("url").isEmpty()
          && !queued.contains(candidate.optString("url"))) {
        next = candidate;
        break;
      }
    }
    recommendations = remaining;
    if (next == null) return;
    awaitingRecommendation = false;
    continuingQueue = true;
    try {
      // Preserve pause state on an explicit skip. Natural completion already has playWhenReady.
      player.addMediaItem(Track.item(next));
      player.seekTo(player.getMediaItemCount() - 1, 0);
      player.prepare();
    } finally {
      continuingQueue = false;
    }
  }

  private void applyEqualizer() {
    try {
      if (eqSession != player.getAudioSessionId()) {
        if (equalizer != null) equalizer.release();
        equalizer = null;
        eqSession = player.getAudioSessionId();
      }
      if (equalizer == null && eqSession != C.AUDIO_SESSION_ID_UNSET)
        equalizer = new Equalizer(0, eqSession);
      if (tailEqSession != tail.getAudioSessionId()) {
        if (tailEqualizer != null) tailEqualizer.release();
        tailEqualizer = null;
        tailEqSession = tail.getAudioSessionId();
      }
      if (tailEqualizer == null && tailEqSession != C.AUDIO_SESSION_ID_UNSET)
        tailEqualizer = new Equalizer(0, tailEqSession);
      for (Equalizer eq : new Equalizer[] {equalizer, tailEqualizer})
        if (eq != null) {
          JSONObject settings = CrowApp.instance.settings();
          short[] range = eq.getBandLevelRange();
          for (short i = 0; i < eq.getNumberOfBands(); i++) {
            double hz = eq.getCenterFreq(i) / 1000.0;
            int gain =
                hz < 500
                    ? settings.optInt("BASS_GAIN")
                    : hz > 4000 ? settings.optInt("TREBLE_GAIN") : 0;
            eq.setBandLevel(i, (short) Math.max(range[0], Math.min(range[1], gain * 100)));
          }
          eq.setEnabled(true);
        }
    } catch (Exception ignored) {
      /* Some devices don't provide a system equalizer. */
    }
  }

  private void updateFade(long now) {
    JSONObject settings = CrowApp.instance.settings();
    if (!settings.optBoolean("CROSSFADE_ENABLED", false)) {
      if (fading || tailPreparing) cancelFade();
      return;
    }
    if (fading) {
      if (!player.isPlaying()) {
        fadeStart = 0;
        return;
      }
      if (fadeStart == 0) fadeStart = now;
      float fraction = Math.min(1f, (float) (now - fadeStart) / fadeLength);
      player.setVolume(fraction);
      tail.setVolume(1f - fraction);
      if (fraction >= 1) cancelFade();
      return;
    }
    long duration = player.getDuration(), position = player.getCurrentPosition();
    int next = player.getNextMediaItemIndex();
    if (!player.isPlaying()
        || duration <= 0
        || !player.isCurrentMediaItemSeekable()
        || next == C.INDEX_UNSET
        || next == player.getCurrentMediaItemIndex()
        || player.getRepeatMode() == Player.REPEAT_MODE_ONE) return;
    if (!readyId.equals(player.getMediaItemAt(next).mediaId)) return;
    fadeLength = settings.optInt("CROSSFADE_DURATION", 5) * 1000;
    if (duration < fadeLength * 3L || duration - position > fadeLength + 1200 || tailPreparing)
      return;
    MediaItem current = player.getCurrentMediaItem();
    if (current == null) return;
    tailPreparing = true;
    int generation = ++tailGeneration;
    tail.setMediaItem(current);
    tail.seekTo(position);
    tail.setVolume(0);
    tail.prepare();
    Runnable begin =
        new Runnable() {
          public void run() {
            if (!tailPreparing || generation != tailGeneration || destroyed) return;
            if (!player.isPlaying()
                || !Objects.equals(
                    current.mediaId,
                    player.getCurrentMediaItem() == null
                        ? ""
                        : player.getCurrentMediaItem().mediaId)) {
              cancelFade();
              return;
            }
            if (tail.getPlaybackState() != Player.STATE_READY) {
              handler.postDelayed(this, 100);
              return;
            }
            tail.seekTo(player.getCurrentPosition());
            tail.setVolume(1);
            tail.play();
            fading = true;
            tailPreparing = false;
            fadeStart = SystemClock.elapsedRealtime();
            player.setVolume(0);
            player.seekToNextMediaItem();
          }
        };
    handler.post(begin);
  }

  private void cancelFade() {
    tailGeneration++;
    tailPreparing = false;
    fading = false;
    if (tail != null) {
      tail.stop();
      tail.clearMediaItems();
    }
    if (player != null) player.setVolume(1);
  }

  @Override
  public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
    return session;
  }

  @Override
  public void onDestroy() {
    destroyed = true;
    recommendationLoading = false;
    active = null;
    recommendationGeneration++;
    handler.removeCallbacksAndMessages(null);
    unregisterReceiver(settingsChanged);
    if (prefetch != null) prefetch.cancel();
    prefetchExecutor.shutdownNow();
    if (equalizer != null) equalizer.release();
    if (tailEqualizer != null) tailEqualizer.release();
    tail.release();
    player.release();
    session.release();
    // Cache belongs to the application process so a service restart can reuse it safely.
    super.onDestroy();
  }
}
