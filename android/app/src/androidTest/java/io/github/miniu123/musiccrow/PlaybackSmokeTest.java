package io.github.miniu123.musiccrow;

import static org.junit.Assert.*;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.*;
import androidx.media3.common.*;
import androidx.media3.session.*;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.google.common.util.concurrent.ListenableFuture;
import java.io.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class PlaybackSmokeTest {
  Instrumentation instrumentation;
  Context context;
  Activity activity;
  MediaController controller;
  CrowApp app;

  @Before
  public void setup() throws Exception {
    instrumentation = InstrumentationRegistry.getInstrumentation();
    context = instrumentation.getTargetContext();
    app = (CrowApp) context.getApplicationContext();
    app.call("state", new JSONObject());
    activity =
        instrumentation.startActivitySync(
            new Intent(context, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    ListenableFuture<MediaController>[] pending = new ListenableFuture[1];
    instrumentation.runOnMainSync(
        () ->
            pending[0] =
                new MediaController.Builder(
                        context,
                        new SessionToken(
                            context, new ComponentName(context, PlaybackService.class)))
                    .buildAsync());
    controller = pending[0].get(15, TimeUnit.SECONDS);
  }

  @After
  public void cleanup() {
    instrumentation.runOnMainSync(
        () -> {
          if (controller != null) {
            controller.stop();
            controller.clearMediaItems();
            controller.setVolume(1);
            controller.release();
          }
          if (activity != null) activity.finish();
        });
    for (File audio : continuationAudio) audio.delete();
  }

  private void await(Callable<Boolean> condition, int seconds) throws Exception {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(seconds);
    while (System.nanoTime() < deadline) {
      FutureTask<Boolean> check = new FutureTask<>(condition);
      instrumentation.runOnMainSync(check);
      if (check.get()) return;
      Thread.sleep(100);
    }
    instrumentation.runOnMainSync(
        () ->
            fail(
                "Playback condition timed out; state="
                    + controller.getPlaybackState()
                    + "; playing="
                    + controller.isPlaying()
                    + "; ready="
                    + controller.getPlayWhenReady()
                    + "; suppression="
                    + controller.getPlaybackSuppressionReason()
                    + "; items="
                    + controller.getMediaItemCount()
                    + "; index="
                    + controller.getCurrentMediaItemIndex()
                    + "; position="
                    + controller.getCurrentPosition()
                    + "; error="
                    + controller.getPlayerError()));
  }

  @Test
  public void onlineAudioActuallyDecodesAndContinuesInBackground() throws Exception {
    JSONObject found =
        new JSONObject(app.source("search", "Kevin MacLeod Carefree", "YouTube Music"));
    JSONObject track = found.getJSONArray("tracks").getJSONObject(0);
    instrumentation.runOnMainSync(
        () -> {
          PlaybackService.active.startSession();
          controller.setVolume(0);
          controller.setMediaItem(Track.item(track));
          controller.prepare();
          controller.play();
        });
    await(() -> controller.isPlaying() && controller.getCurrentPosition() > 500, 45);
    instrumentation.runOnMainSync(() -> activity.finish());
    await(() -> controller.isPlaying() && controller.getCurrentPosition() > 2000, 10);
    instrumentation.runOnMainSync(() -> assertNull(controller.getPlayerError()));
  }

  @Test
  public void searchSelectionPlaysOneSongWhilePlaylistKeepsItsQueue() throws Exception {
    File audio = new File(context.getCacheDir(), "test-selection.wav");
    int samples = 44100 * 18;
    ByteBuffer bytes = ByteBuffer.allocate(44 + samples * 2).order(ByteOrder.LITTLE_ENDIAN);
    bytes
        .put("RIFF".getBytes())
        .putInt(36 + samples * 2)
        .put("WAVEfmt ".getBytes())
        .putInt(16)
        .putShort((short) 1)
        .putShort((short) 1)
        .putInt(44100)
        .putInt(88200)
        .putShort((short) 2)
        .putShort((short) 16)
        .put("data".getBytes())
        .putInt(samples * 2);
    try (FileOutputStream output = new FileOutputStream(audio)) {
      output.write(bytes.array());
    }
    java.lang.reflect.Field bound = MainActivity.class.getDeclaredField("controller");
    bound.setAccessible(true);
    await(() -> bound.get(activity) != null, 10);
    java.lang.reflect.Method select =
        MainActivity.class.getDeclaredMethod(
            "playSelection", JSONObject.class, JSONArray.class, int.class, String.class);
    select.setAccessible(true);
    JSONObject a =
        CrowApp.obj("title", "Preview A", "url", audio.toURI().toString(), "duration", 18);
    JSONObject b =
        CrowApp.obj("title", "Preview B", "url", audio.toURI().toString(), "duration", 18);
    JSONArray results = new JSONArray().put(a).put(b);
    try {
      instrumentation.runOnMainSync(
          () -> {
            try {
              controller.setVolume(0);
              select.invoke(activity, b, results, 1, "");
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      await(
          () ->
              controller.getMediaItemCount() == 1
                  && "Preview B"
                      .equals(String.valueOf(controller.getCurrentMediaItem().mediaMetadata.title)),
          10);
      instrumentation.runOnMainSync(
          () -> {
            try {
              select.invoke(activity, b, results, 1, "Fixture playlist");
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      await(
          () -> controller.getMediaItemCount() == 2 && controller.getCurrentMediaItemIndex() == 1,
          10);
      instrumentation.runOnMainSync(() -> assertNull(controller.getPlayerError()));
    } finally {
      instrumentation.runOnMainSync(() -> controller.stop());
      audio.delete();
    }
  }

  private final List<File> continuationAudio = new ArrayList<>();

  private JSONObject continuationTrack(String title) throws Exception {
    File audio = File.createTempFile("continuation-", ".wav", context.getCacheDir());
    continuationAudio.add(audio);
    int samples = 44100 * 18;
    ByteBuffer bytes = ByteBuffer.allocate(44 + samples * 2).order(ByteOrder.LITTLE_ENDIAN);
    bytes
        .put("RIFF".getBytes())
        .putInt(36 + samples * 2)
        .put("WAVEfmt ".getBytes())
        .putInt(16)
        .putShort((short) 1)
        .putShort((short) 1)
        .putInt(44100)
        .putInt(88200)
        .putShort((short) 2)
        .putShort((short) 16)
        .put("data".getBytes())
        .putInt(samples * 2);
    try (FileOutputStream output = new FileOutputStream(audio)) {
      output.write(bytes.array());
    }
    return CrowApp.obj("title", title, "url", audio.toURI().toString(), "duration", 18);
  }

  // Freeze background discovery so these tests exercise playback with deterministic candidates.
  private int freezeRecommendations(JSONObject... candidates) {
    try {
      java.lang.reflect.Field generation =
          PlaybackService.class.getDeclaredField("recommendationGeneration");
      generation.setAccessible(true);
      int value = generation.getInt(PlaybackService.active) + 1;
      generation.setInt(PlaybackService.active, value);
      PlaybackService.recommendations = new ArrayList<>(Arrays.asList(candidates));
      return value;
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }

  private void deliverRecommendations(JSONObject... candidates) {
    try {
      int generation = freezeRecommendations();
      java.lang.reflect.Method publish =
          PlaybackService.class.getDeclaredMethod(
              "publishRecommendations", JSONObject.class, int.class);
      publish.setAccessible(true);
      publish.invoke(
          PlaybackService.active,
          CrowApp.obj("tracks", new JSONArray(Arrays.asList(candidates))),
          generation);
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }

  private void startContinuation(JSONObject... tracks) throws Exception {
    instrumentation.runOnMainSync(
        () -> {
          PlaybackService.active.startSession();
          controller.setRepeatMode(Player.REPEAT_MODE_OFF);
          controller.setShuffleModeEnabled(false);
          List<MediaItem> items = new ArrayList<>();
          for (JSONObject track : tracks) items.add(Track.item(track));
          controller.setMediaItems(items);
          controller.prepare();
          controller.play();
        });
    await(() -> controller.isPlaying(), 10);
    instrumentation.runOnMainSync(() -> freezeRecommendations());
  }

  private boolean current(JSONObject track) {
    return controller.getCurrentMediaItem() != null
        && track.optString("url").equals(controller.getCurrentMediaItem().mediaId);
  }

  @Test
  public void nextUsesQueueFirstThenSuggestionsForBothControllerCommands() throws Exception {
    JSONObject a = continuationTrack("Start"),
        b = continuationTrack("Queued"),
        c = continuationTrack("Suggested"),
        d = continuationTrack("More");
    startContinuation(a, b);
    instrumentation.runOnMainSync(
        () -> {
          freezeRecommendations(c);
          controller.seekToNextMediaItem();
        });
    await(() -> current(b) && controller.isPlaying(), 10);
    instrumentation.runOnMainSync(
        () -> {
          assertEquals(2, controller.getMediaItemCount());
          assertTrue(controller.isCommandAvailable(Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM));
          freezeRecommendations(
              a, b, c, c); // Stale/duplicate candidates must not restart old tracks.
          controller.seekToNextMediaItem();
        });
    await(() -> current(c) && controller.isPlaying(), 10);
    instrumentation.runOnMainSync(
        () -> {
          assertEquals(3, controller.getMediaItemCount());
          assertTrue(controller.isCommandAvailable(Player.COMMAND_SEEK_TO_NEXT));
          freezeRecommendations(d);
          controller.seekToNext();
        });
    await(() -> current(d) && controller.isPlaying(), 10);
  }

  @Test
  public void completionUsesReadyAndLateSuggestions() throws Exception {
    JSONObject a = continuationTrack("Start"),
        b = continuationTrack("Ready suggestion"),
        c = continuationTrack("Late suggestion");
    startContinuation(a);
    instrumentation.runOnMainSync(
        () -> {
          freezeRecommendations(b);
          controller.seekTo(17800);
        });
    await(() -> current(b) && controller.isPlaying(), 10);
    instrumentation.runOnMainSync(
        () -> {
          freezeRecommendations();
          controller.seekTo(17800);
        });
    await(() -> controller.getPlaybackState() == Player.STATE_ENDED, 10);
    instrumentation.runOnMainSync(() -> deliverRecommendations(c));
    await(() -> current(c) && controller.isPlaying(), 10);
  }

  @Test
  public void pendingSkipUsesLateSuggestionAndStopCancelsContinuation() throws Exception {
    JSONObject a = continuationTrack("Start"),
        b = continuationTrack("Late suggestion"),
        c = continuationTrack("After stop");
    startContinuation(a);
    instrumentation.runOnMainSync(
        () -> {
          freezeRecommendations();
          controller.seekToNextMediaItem();
        });
    java.lang.reflect.Field pending =
        PlaybackService.class.getDeclaredField("awaitingRecommendation");
    pending.setAccessible(true);
    await(() -> pending.getBoolean(PlaybackService.active), 5);
    instrumentation.runOnMainSync(() -> deliverRecommendations(b));
    await(() -> current(b) && controller.isPlaying(), 10);
    instrumentation.runOnMainSync(
        () -> {
          freezeRecommendations();
          controller.seekToNext();
        });
    await(() -> pending.getBoolean(PlaybackService.active), 5);
    instrumentation.runOnMainSync(() -> controller.stop());
    await(() -> controller.getPlaybackState() == Player.STATE_IDLE, 5);
    instrumentation.runOnMainSync(() -> deliverRecommendations(c));
    instrumentation.waitForIdleSync();
    instrumentation.runOnMainSync(
        () -> {
          assertTrue(current(b));
          assertEquals(2, controller.getMediaItemCount());
          assertEquals(Player.STATE_IDLE, controller.getPlaybackState());
        });
  }

  @Test
  public void pausedSkipStaysPausedAndRepeatOneDoesNotAutoplay() throws Exception {
    JSONObject a = continuationTrack("Start"),
        b = continuationTrack("Paused suggestion"),
        c = continuationTrack("Not yet");
    startContinuation(a);
    instrumentation.runOnMainSync(() -> controller.pause());
    await(() -> !controller.getPlayWhenReady(), 5);
    instrumentation.runOnMainSync(
        () -> {
          freezeRecommendations(b);
          controller.seekToNext();
        });
    await(() -> current(b) && controller.getPlaybackState() == Player.STATE_READY, 10);
    instrumentation.runOnMainSync(
        () -> {
          assertFalse(controller.getPlayWhenReady());
          controller.setRepeatMode(Player.REPEAT_MODE_ONE);
          freezeRecommendations(c);
          controller.seekTo(17800);
          controller.play();
        });
    await(() -> controller.isPlaying() && controller.getCurrentPosition() < 2000, 10);
    instrumentation.runOnMainSync(
        () -> {
          assertTrue(current(b));
          assertEquals(2, controller.getMediaItemCount());
          controller.setRepeatMode(Player.REPEAT_MODE_OFF);
        });
  }

  @Test
  public void stoppedSkipStaysStopped() throws Exception {
    JSONObject a = continuationTrack("Playing"), b = continuationTrack("After stop");
    startContinuation(a);
    instrumentation.runOnMainSync(
        () -> {
          PlaybackService.active.stopPlayback();
          freezeRecommendations(b);
          controller.seekToNext();
        });
    await(() -> current(b), 10);
    Thread.sleep(1500);
    instrumentation.runOnMainSync(
        () -> {
          assertFalse(controller.getPlayWhenReady());
          assertFalse(controller.isPlaying());
        });
  }

  private Object serviceField(String name) throws Exception {
    java.lang.reflect.Field field = PlaybackService.class.getDeclaredField(name);
    field.setAccessible(true);
    return field.get(PlaybackService.active);
  }

  private void serviceField(String name, Object value) throws Exception {
    java.lang.reflect.Field field = PlaybackService.class.getDeclaredField(name);
    field.setAccessible(true);
    field.set(PlaybackService.active, value);
  }

  @Test
  public void preparesSuggestionWhenQueueRunsOutAndHonorsRemovalAndSetting() throws Exception {
    JSONObject a = continuationTrack("Start"),
        b = continuationTrack("Queued"),
        c = continuationTrack("Suggested"),
        d = continuationTrack("Replacement");
    boolean original = app.settings().optBoolean("PREFETCH_ENABLED", true);
    try {
      app.settings().put("PREFETCH_ENABLED", true);
      startContinuation(a, b);
      instrumentation.runOnMainSync(() -> deliverRecommendations(c));
      await(() -> b.optString("url").equals(serviceField("readyId")), 5);
      instrumentation.runOnMainSync(() -> controller.seekToNext());
      await(() -> current(b), 5);
      instrumentation.runOnMainSync(() -> deliverRecommendations(c));
      await(() -> c.optString("url").equals(serviceField("readyId")), 5);
      instrumentation.runOnMainSync(
          () -> {
            assertEquals(
                2, controller.getMediaItemCount()); // Preparation doesn't add a normal queue item.
            deliverRecommendations(c, d);
            PlaybackService.active.removeRecommendation(
                c); // Remove while a later batch is pending.
          });
      await(() -> d.optString("url").equals(serviceField("readyId")), 5);
      instrumentation.runOnMainSync(
          () -> {
            assertEquals(1, PlaybackService.recommendations.size());
            assertEquals(
                d.optString("url"), PlaybackService.recommendations.get(0).optString("url"));
          });
      app.settings().put("PREFETCH_ENABLED", false);
      context.sendBroadcast(new Intent(CrowApp.CHANGED).setPackage(context.getPackageName()));
      await(() -> "".equals(serviceField("prefetchId")), 5);
    } finally {
      app.settings().put("PREFETCH_ENABLED", original);
    }
  }

  @Test
  public void reopeningKeepsCachedSuggestionsAndDoesNotRestartDiscovery() throws Exception {
    JSONObject a = continuationTrack("Start"), b = continuationTrack("Cached original");
    a.put("artist", "Cache Artist");
    b.put("artist", "Cache Artist").put("duration", 180);
    startContinuation(a);
    instrumentation.runOnMainSync(
        () -> {
          try {
            freezeRecommendations(b);
            PlaybackService.recommendationLoading = false;
            serviceField("discoveryCache", new ArrayList<>(Arrays.asList(b)));
            serviceField("discoveryContext", a.optString("url"));
            serviceField("lastDiscovery", android.os.SystemClock.elapsedRealtime());
            PlaybackService.active.refreshRecommendations(false);
            int generation = (Integer) serviceField("recommendationGeneration");
            PlaybackService.active.refreshRecommendations(false);
            assertEquals(generation, serviceField("recommendationGeneration"));
            assertFalse(PlaybackService.recommendations.isEmpty());
          } catch (Exception e) {
            throw new RuntimeException(e);
          }
        });
    await(() -> !PlaybackService.recommendationLoading, 10);
    instrumentation.runOnMainSync(
        () -> {
          assertFalse(PlaybackService.recommendationFailed);
          assertEquals(b.optString("url"), PlaybackService.recommendations.get(0).optString("url"));
        });
  }

  @Test
  public void pauseButtonCancelsLoadingAndReplayKeepsCurrentTrack() throws Exception {
    JSONObject a = continuationTrack("First"), b = continuationTrack("Last");
    java.lang.reflect.Field bound = MainActivity.class.getDeclaredField("controller");
    bound.setAccessible(true);
    await(() -> bound.get(activity) != null, 10);
    java.lang.reflect.Method toggle = MainActivity.class.getDeclaredMethod("togglePlayback");
    toggle.setAccessible(true);
    instrumentation.runOnMainSync(
        () -> {
          Object original = null;
          try {
            original = bound.get(activity);
            bound.set(activity, controller);
            PlaybackService.active.startSession();
            controller.setRepeatMode(Player.REPEAT_MODE_OFF);
            controller.setMediaItems(Arrays.asList(Track.item(a), Track.item(b)), 1, 0);
            controller.prepare();
            controller.play();
            assertEquals(Player.STATE_BUFFERING, controller.getPlaybackState());
            toggle.invoke(activity);
            assertFalse(controller.getPlayWhenReady());
          } catch (Exception e) {
            throw new RuntimeException(e);
          } finally {
            try {
              bound.set(activity, original);
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          }
        });
    await(
        () ->
            controller.getPlaybackState() == Player.STATE_READY
                && current(b)
                && !controller.getPlayWhenReady(),
        10);
    instrumentation.runOnMainSync(
        () -> {
          freezeRecommendations();
          controller.seekTo(17800);
          controller.play();
        });
    await(() -> controller.getPlaybackState() == Player.STATE_ENDED, 10);
    instrumentation.runOnMainSync(
        () -> {
          try {
            toggle.invoke(activity);
          } catch (Exception e) {
            throw new RuntimeException(e);
          }
        });
    await(() -> current(b) && controller.isPlaying(), 10);
  }

  @Test
  public void onlineSuggestionPrefetchesWithoutAddingQueueEntry() throws Exception {
    JSONObject a = continuationTrack("Prefetch fixture");
    a.put("artist", "Kevin MacLeod");
    JSONObject found =
        new JSONObject(app.source("discover", "Kevin MacLeod", "YouTube Music", false));
    JSONObject ranked =
        new JSONObject(
            app.call(
                "recommend",
                CrowApp.obj(
                    "context",
                    new JSONArray().put(a),
                    "discoveries",
                    found.getJSONArray("tracks"))));
    JSONObject suggestion = ranked.getJSONArray("tracks").getJSONObject(0);
    boolean original = app.settings().optBoolean("PREFETCH_ENABLED", true);
    try {
      app.settings().put("PREFETCH_ENABLED", true);
      startContinuation(a);
      instrumentation.runOnMainSync(() -> controller.pause());
      await(() -> !controller.getPlayWhenReady(), 5);
      instrumentation.runOnMainSync(() -> deliverRecommendations(suggestion));
      await(() -> suggestion.optString("url").equals(serviceField("readyId")), 90);
      instrumentation.runOnMainSync(
          () -> {
            assertEquals(1, controller.getMediaItemCount());
            assertTrue(current(a));
            String key = Track.item(suggestion).localConfiguration.uri.toString();
            assertTrue(
                "Suggestion audio must be cached",
                AudioSources.get(context).cache.getCachedBytes(key, 0, C.LENGTH_UNSET) > 0);
          });
    } finally {
      app.settings().put("PREFETCH_ENABLED", original);
    }
  }

  @Test
  public void localCrossfadeAdvancesToNextAndCompletes() throws Exception {
    File audio = new File(context.getCacheDir(), "test-silence.wav");
    int samples = 44100 * 18;
    ByteBuffer bytes = ByteBuffer.allocate(44 + samples * 2).order(ByteOrder.LITTLE_ENDIAN);
    bytes
        .put("RIFF".getBytes())
        .putInt(36 + samples * 2)
        .put("WAVEfmt ".getBytes())
        .putInt(16)
        .putShort((short) 1)
        .putShort((short) 1)
        .putInt(44100)
        .putInt(88200)
        .putShort((short) 2)
        .putShort((short) 16)
        .put("data".getBytes())
        .putInt(samples * 2);
    try (FileOutputStream output = new FileOutputStream(audio)) {
      output.write(bytes.array());
    }
    boolean original = app.settings().optBoolean("CROSSFADE_ENABLED");
    int duration = app.settings().optInt("CROSSFADE_DURATION", 5);
    try {
      app.settings().put("CROSSFADE_ENABLED", true).put("CROSSFADE_DURATION", 5);
      JSONObject a =
          CrowApp.obj("title", "Silence A", "url", audio.toURI().toString(), "duration", 18);
      JSONObject b =
          CrowApp.obj("title", "Silence B", "url", audio.toURI().toString(), "duration", 18);
      instrumentation.runOnMainSync(
          () -> {
            PlaybackService.active.startSession();
            controller.setMediaItems(Arrays.asList(Track.item(a), Track.item(b)));
            controller.prepare();
            controller.play();
          });
      await(() -> controller.isPlaying(), 10);
      instrumentation.runOnMainSync(() -> controller.seekTo(13000));
      await(() -> controller.getCurrentMediaItemIndex() == 1 && controller.isPlaying(), 10);
      await(() -> controller.getVolume() >= 0.99f, 8);
      instrumentation.runOnMainSync(() -> assertNull(controller.getPlayerError()));
    } finally {
      app.settings().put("CROSSFADE_ENABLED", original).put("CROSSFADE_DURATION", duration);
      audio.delete();
    }
  }
}
