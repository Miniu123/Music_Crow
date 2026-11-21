package io.github.miniu123.musiccrow;

import static org.junit.Assert.*;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.view.*;
import android.widget.*;
import androidx.media3.common.*;
import androidx.media3.session.MediaController;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

/** Device UI smoke test: navigation, constrained layout and live expanded-player metadata. */
@RunWith(AndroidJUnit4.class)
public class InterfaceTest {
  private Instrumentation instrumentation;
  private MainActivity activity;

  private Object field(String name) throws Exception {
    Field field = MainActivity.class.getDeclaredField(name);
    field.setAccessible(true);
    return field.get(activity);
  }

  private void main(Runnable work) {
    instrumentation.runOnMainSync(work);
  }

  private void ready(Callable<Boolean> check) throws Exception {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
    while (System.nanoTime() < deadline) {
      FutureTask<Boolean> result = new FutureTask<>(check);
      main(result);
      if (result.get()) return;
      Thread.sleep(100);
    }
    FutureTask<String> diagnostic =
        new FutureTask<>(
            () -> {
              androidx.core.view.WindowInsetsCompat insets =
                  androidx.core.view.ViewCompat.getRootWindowInsets(
                      activity.getWindow().getDecorView());
              return "focus="
                  + activity.hasWindowFocus()
                  + "; fullscreen="
                  + activity
                      .getSharedPreferences("appearance", Context.MODE_PRIVATE)
                      .getBoolean("fullscreen", true)
                  + "; status="
                  + (insets == null
                      ? "null"
                      : insets.isVisible(androidx.core.view.WindowInsetsCompat.Type.statusBars()))
                  + "; navigation="
                  + (insets == null
                      ? "null"
                      : insets.isVisible(
                          androidx.core.view.WindowInsetsCompat.Type.navigationBars()));
            });
    main(diagnostic);
    fail("Activity did not become ready; " + diagnostic.get());
  }

  private void snapshot(String name) throws Exception {
    ready(() -> ((View) field("content")).getAlpha() >= 0.99f);
    instrumentation.waitForIdleSync();
    FutureTask<Void> capture =
        new FutureTask<>(
            () -> {
              Dialog dialog = (Dialog) field("playerDialog");
              View view =
                  dialog != null && dialog.isShowing()
                      ? dialog.getWindow().getDecorView()
                      : activity.getWindow().getDecorView();
              assertTrue("View must be measured", view.getWidth() > 0 && view.getHeight() > 0);
              Bitmap bitmap =
                  Bitmap.createBitmap(view.getWidth(), view.getHeight(), Bitmap.Config.ARGB_8888);
              view.draw(new Canvas(bitmap));
              File directory = new File(activity.getExternalFilesDir(null), "ui-review");
              directory.mkdirs();
              try (FileOutputStream out =
                  new FileOutputStream(new File(directory, name + ".png"))) {
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
              }
              bitmap.recycle();
              return null;
            });
    main(capture);
    capture.get();
  }

  @Test
  public void youtubeMusicImportIsAccessibleAndSavesASeparatePlaylist() throws Exception {
    instrumentation = InstrumentationRegistry.getInstrumentation();
    Context context = instrumentation.getTargetContext();
    CrowApp app = (CrowApp) context.getApplicationContext();
    String name = "Import test " + System.nanoTime();
    activity =
        (MainActivity)
            instrumentation.startActivitySync(
                new Intent(context, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    org.json.JSONArray tracks =
        new org.json.JSONArray()
            .put(
                CrowApp.obj(
                    "title",
                    "First",
                    "url",
                    "https://youtu.be/import-fixture-first",
                    "duration",
                    180))
            .put(
                CrowApp.obj(
                    "title",
                    "Second",
                    "url",
                    "https://youtu.be/import-fixture-second",
                    "duration",
                    180));
    try {
      ready(() -> (boolean) field("loaded"));
      main(
          () -> {
            try {
              ((List<TextView>) field("navigationItems")).get(2).performClick();
              View button =
                  activity.getWindow().getDecorView().findViewWithTag("import-youtube-music");
              assertNotNull(button);
              button.performClick();
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      instrumentation.waitForIdleSync();
      main(
          () -> {
            try {
              AlertDialog dialog = (AlertDialog) field("playlistImportDialog");
              assertNotNull(dialog.findViewById(android.R.id.button1));
              assertNotNull(
                  dialog.getWindow().getDecorView().findViewWithTag("playlist-import-url"));
              dialog.getButton(AlertDialog.BUTTON_POSITIVE).performClick();
              assertTrue(dialog.isShowing()); // Empty URLs never start network work.
              dialog.dismiss();
              Method preview =
                  MainActivity.class.getDeclaredMethod(
                      "previewPlaylistImport", org.json.JSONObject.class);
              preview.setAccessible(true);
              preview.invoke(activity, CrowApp.obj("title", name, "tracks", tracks, "skipped", 1));
              dialog = (AlertDialog) field("playlistImportDialog");
              EditText input =
                  dialog.getWindow().getDecorView().findViewWithTag("playlist-import-name");
              assertEquals(name, input.getText().toString());
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      instrumentation.waitForIdleSync();
      main(
          () -> {
            try {
              ((AlertDialog) field("playlistImportDialog"))
                  .getButton(AlertDialog.BUTTON_POSITIVE)
                  .performClick();
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      ready(
          () -> {
            AlertDialog dialog = (AlertDialog) field("playlistImportDialog");
            EditText input =
                dialog.getWindow().getDecorView().findViewWithTag("playlist-import-name");
            if (input != null) assertNull("Import failed: " + input.getError(), input.getError());
            return app.state.getJSONObject("playlists").has(name);
          });
      main(
          () -> {
            try {
              org.json.JSONArray saved =
                  app.state.getJSONObject("playlists").getJSONObject(name).getJSONArray("tracks");
              assertEquals(2, saved.length());
              assertEquals("First", saved.getJSONObject(0).getString("title"));
              assertEquals("Second", saved.getJSONObject(1).getString("title"));
              Method preview =
                  MainActivity.class.getDeclaredMethod(
                      "previewPlaylistImport", org.json.JSONObject.class);
              preview.setAccessible(true);
              preview.invoke(activity, CrowApp.obj("title", name, "tracks", tracks));
              AlertDialog dialog = (AlertDialog) field("playlistImportDialog");
              EditText input =
                  dialog.getWindow().getDecorView().findViewWithTag("playlist-import-name");
              assertEquals(name + " (2)", input.getText().toString());
              input.setText(name);
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      instrumentation.waitForIdleSync();
      main(
          () -> {
            try {
              AlertDialog dialog = (AlertDialog) field("playlistImportDialog");
              EditText input =
                  dialog.getWindow().getDecorView().findViewWithTag("playlist-import-name");
              dialog.getButton(AlertDialog.BUTTON_POSITIVE).performClick();
              assertTrue(dialog.isShowing());
              assertNotNull(input.getError());
              dialog.dismiss();
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
    } finally {
      if (app.state.getJSONObject("playlists").has(name))
        app.call("delete", CrowApp.obj("name", name));
      main(() -> activity.finish());
    }
  }

  @Test
  public void settingsHaveNoFullscreenSwitchAndBarsStayVisible() throws Exception {
    instrumentation = InstrumentationRegistry.getInstrumentation();
    Context context = instrumentation.getTargetContext();
    activity =
        (MainActivity)
            instrumentation.startActivitySync(
                new Intent(context, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    try {
      ready(() -> (boolean) field("loaded"));
      main(
          () -> {
            try {
              ((List<TextView>) field("navigationItems")).get(4).performClick();
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      ready(
          () -> {
            androidx.core.view.WindowInsetsCompat insets =
                androidx.core.view.ViewCompat.getRootWindowInsets(
                    activity.getWindow().getDecorView());
            return insets != null
                && insets.isVisible(androidx.core.view.WindowInsetsCompat.Type.statusBars())
                && insets.isVisible(androidx.core.view.WindowInsetsCompat.Type.navigationBars());
          });
      FutureTask<Boolean> missing =
          new FutureTask<>(
              () -> activity.getWindow().getDecorView().findViewWithTag("fullscreen-toggle") == null);
      main(missing);
      assertTrue("The full-screen switch should be gone", missing.get());
      FutureTask<Boolean> logo =
          new FutureTask<>(
              () -> activity.getWindow().getDecorView().findViewWithTag("author-logo") != null);
      main(logo);
      assertTrue("The author's logo is shown in About", logo.get());
    } finally {
      main(() -> activity.finish());
    }
  }

  @Test
  public void draggingAQueueTrackMovesIt() throws Exception {
    instrumentation = InstrumentationRegistry.getInstrumentation();
    Context context = instrumentation.getTargetContext();
    activity =
        (MainActivity)
            instrumentation.startActivitySync(
                new Intent(context, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    MediaController[] player = new MediaController[1];
    List<MediaItem> original = new ArrayList<>();
    int[] index = new int[1];
    long[] position = new long[1];
    try {
      ready(() -> (boolean) field("loaded") && field("controller") != null);
      main(
          () -> {
            try {
              player[0] = (MediaController) field("controller");
              for (int i = 0; i < player[0].getMediaItemCount(); i++)
                original.add(player[0].getMediaItemAt(i));
              index[0] = Math.max(0, player[0].getCurrentMediaItemIndex());
              position[0] = Math.max(0, player[0].getCurrentPosition());
              player[0].pause();
              player[0].stop();
              List<MediaItem> queue = new ArrayList<>();
              for (String title : new String[] {"Teraz", "A", "B", "C", "D"})
                queue.add(
                    Track.item(CrowApp.obj("title", title, "url", "file:///drag-test-" + title)));
              player[0].setMediaItems(queue, 0, 0);
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      ready(() -> player[0].getMediaItemCount() == 5);
      // Rows after the current track: A B C D. Slot 0 is before A, slot 4 after D.
      drag(0, 4, 0, 1, 0); // D above A
      assertEquals(Arrays.asList("Teraz", "D", "A", "B", "C"), titles(player[0]));
      drag(0, 2, 0, 1, 3); // A below B
      assertEquals(Arrays.asList("Teraz", "D", "B", "A", "C"), titles(player[0]));
      ready(() -> PlaybackService.active != null);
      List<JSONObject> savedSuggestions = PlaybackService.recommendations;
      try {
        JSONObject s1 = CrowApp.obj("title", "S1", "url", "file:///drag-test-S1");
        JSONObject s2 = CrowApp.obj("title", "S2", "url", "file:///drag-test-S2");
        JSONObject s3 = CrowApp.obj("title", "S3", "url", "file:///drag-test-S3");
        PlaybackService.recommendations = new ArrayList<>(Arrays.asList(s1, s2, s3));
        dragSuggestion(s3, 1, 0, 0); // S3 to the top of the suggestions
        assertEquals("S3", PlaybackService.recommendations.get(0).optString("title"));
        int[] next = new int[1];
        main(() -> next[0] = player[0].getCurrentMediaItemIndex() + 1);
        dragSuggestion(s1, 0, 0, next[0]); // S1 into the queue, right after the current track
        assertEquals("S1", titles(player[0]).get(next[0]));
        assertEquals(6, titles(player[0]).size());
        for (JSONObject t : PlaybackService.recommendations)
          assertNotEquals("S1", t.optString("title"));
      } finally {
        PlaybackService.recommendations = savedSuggestions;
      }
    } finally {
      main(
          () -> {
            if (player[0] != null) {
              if (original.isEmpty()) player[0].clearMediaItems();
              else player[0].setMediaItems(original, index[0], position[0]);
            }
            activity.finish();
          });
    }
  }

  @Test
  public void expandedPlayerShowsSuggestionsBelowTheQueue() throws Exception {
    instrumentation = InstrumentationRegistry.getInstrumentation();
    Context context = instrumentation.getTargetContext();
    activity =
        (MainActivity)
            instrumentation.startActivitySync(
                new Intent(context, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    MediaController[] player = new MediaController[1];
    List<MediaItem> original = new ArrayList<>();
    int[] index = new int[1];
    long[] position = new long[1];
    List<JSONObject> savedSuggestions = PlaybackService.recommendations;
    try {
      ready(() -> (boolean) field("loaded") && field("controller") != null);
      main(
          () -> {
            try {
              player[0] = (MediaController) field("controller");
              for (int i = 0; i < player[0].getMediaItemCount(); i++)
                original.add(player[0].getMediaItemAt(i));
              index[0] = Math.max(0, player[0].getCurrentMediaItemIndex());
              position[0] = Math.max(0, player[0].getCurrentPosition());
              player[0].pause();
              List<MediaItem> queue = new ArrayList<>();
              for (String title : new String[] {"Teraz", "Q1", "Q2"})
                queue.add(Track.item(CrowApp.obj("title", title, "url", "file:///sections-" + title)));
              player[0].setMediaItems(queue, 0, 0);
              PlaybackService.recommendations =
                  new ArrayList<>(
                      Arrays.asList(
                          CrowApp.obj("title", "P1", "url", "file:///sections-P1"),
                          CrowApp.obj("title", "P2", "url", "file:///sections-P2")));
              Method open = MainActivity.class.getDeclaredMethod("fullPlayer");
              open.setAccessible(true);
              open.invoke(activity);
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      ready(() -> field("playerQueue") != null && PlaybackService.active != null);
      Thread.sleep(500); // let the service react to the new queue first
      main(
          () -> {
            try {
              // Freeze discovery (as the playback tests do) so test suggestions stay put.
              Field generation = PlaybackService.class.getDeclaredField("recommendationGeneration");
              generation.setAccessible(true);
              generation.setInt(PlaybackService.active, generation.getInt(PlaybackService.active) + 1);
              PlaybackService.recommendationLoading = false;
              PlaybackService.recommendations =
                  new ArrayList<>(
                      Arrays.asList(
                          CrowApp.obj("title", "P1", "url", "file:///sections-P1"),
                          CrowApp.obj("title", "P2", "url", "file:///sections-P2")));
              Method render = MainActivity.class.getDeclaredMethod("renderPlayerQueue");
              render.setAccessible(true);
              render.invoke(activity);
            } catch (Exception e) {
              throw new RuntimeException(e);
            }
          });
      FutureTask<int[]> layout =
          new FutureTask<>(
              () -> {
                LinearLayout box = (LinearLayout) field("playerQueue");
                View queue = box.findViewWithTag("player-queue");
                View suggestions = box.findViewWithTag("player-suggestions");
                return new int[] {
                  queue == null ? -1 : box.indexOfChild(queue),
                  suggestions == null ? -1 : box.indexOfChild(suggestions),
                  queue == null ? 0 : ((ViewGroup) queue).getChildCount(),
                  suggestions == null ? 0 : ((ViewGroup) suggestions).getChildCount()
                };
              });
      main(layout);
      int[] found = layout.get();
      assertTrue("queue section shown", found[0] >= 0);
      assertTrue("suggestions shown below the queue", found[1] > found[0]);
      assertEquals(2, found[2]);
      assertEquals(2, found[3]);
    } finally {
      PlaybackService.recommendations = savedSuggestions;
      main(
          () -> {
            try {
              Dialog dialog = (Dialog) field("playerDialog");
              if (dialog != null) dialog.dismiss();
            } catch (Exception ignored) {
            }
            if (player[0] != null) {
              if (original.isEmpty()) player[0].clearMediaItems();
              else player[0].setMediaItems(original, index[0], position[0]);
            }
            activity.finish();
          });
    }
  }

  private void setDrag(int source, int from, MediaItem item, JSONObject track) throws Exception {
    for (String name : new String[] {"dragSource", "dragFrom", "dragItem", "dragTrack"}) {
      Field f = MainActivity.class.getDeclaredField(name);
      f.setAccessible(true);
      if (name.equals("dragSource")) f.setInt(activity, source);
      else if (name.equals("dragFrom")) f.setInt(activity, from);
      else if (name.equals("dragItem")) f.set(activity, item);
      else f.set(activity, track);
    }
  }

  private void finishDrag(int zone, int start, int slot) throws Exception {
    Method finish =
        MainActivity.class.getDeclaredMethod("finishDrag", int.class, int.class, int.class);
    finish.setAccessible(true);
    finish.invoke(activity, zone, start, slot);
    Method clear = MainActivity.class.getDeclaredMethod("clearDrag");
    clear.setAccessible(true);
    clear.invoke(activity);
  }

  /** Drops queue entry `from` into a zone (0 = queue) whose rows begin at `start`. */
  private void drag(int source, int from, int zone, int start, int slot) throws Exception {
    main(
        () -> {
          try {
            MediaController player = (MediaController) field("controller");
            MediaItem item = player.getMediaItemAt(from);
            setDrag(source, from, item, Track.json(item));
            finishDrag(zone, start, slot);
          } catch (Exception e) {
            throw new RuntimeException(e);
          }
        });
  }

  /** Drops a suggestion into the suggestions list (zone 1) or the queue (zone 0). */
  private void dragSuggestion(JSONObject track, int zone, int slot, int start) throws Exception {
    main(
        () -> {
          try {
            setDrag(1, PlaybackService.recommendations.indexOf(track), null, track);
            finishDrag(zone, start, slot);
          } catch (Exception e) {
            throw new RuntimeException(e);
          }
        });
  }

  private List<String> titles(MediaController player) throws Exception {
    List<String> result = new ArrayList<>();
    FutureTask<Void> read =
        new FutureTask<>(
            () -> {
              for (int i = 0; i < player.getMediaItemCount(); i++)
                result.add(Track.json(player.getMediaItemAt(i)).optString("title"));
              return null;
            });
    main(read);
    read.get();
    return result;
  }

  @Test
  public void navigationAndExpandedPlayerStayUsable() throws Exception {
    instrumentation = InstrumentationRegistry.getInstrumentation();
    Context context = instrumentation.getTargetContext();
    activity =
        (MainActivity)
            instrumentation.startActivitySync(
                new Intent(context, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    MediaController[] player = new MediaController[1];
    List<MediaItem> original = new ArrayList<>();
    long[] position = new long[1];
    int[] index = new int[1];
    boolean[] shuffle = new boolean[1];
    int[] repeat = new int[1];
    try {
      ready(() -> (boolean) field("loaded") && field("controller") != null);
      boolean fullscreen = false; // system bars are always visible
      ready(
          () -> {
            androidx.core.view.WindowInsetsCompat insets =
                androidx.core.view.ViewCompat.getRootWindowInsets(
                    activity.getWindow().getDecorView());
            return insets != null
                && insets.isVisible(androidx.core.view.WindowInsetsCompat.Type.statusBars())
                    != fullscreen
                && insets.isVisible(androidx.core.view.WindowInsetsCompat.Type.navigationBars())
                    != fullscreen;
          });
      main(
          () -> {
            try {
              player[0] = (MediaController) field("controller");
              for (int i = 0; i < player[0].getMediaItemCount(); i++)
                original.add(player[0].getMediaItemAt(i));
              index[0] = Math.max(0, player[0].getCurrentMediaItemIndex());
              position[0] = player[0].getCurrentPosition();
              shuffle[0] = player[0].getShuffleModeEnabled();
              repeat[0] = player[0].getRepeatMode();
              player[0].pause();
              player[0].stop();
              List<MediaItem> preview = new ArrayList<>();
              String[] titles = {
                "Nocne światła",
                "Powrót do domu",
                "Jeszcze jeden raz",
                "Miasto po zmroku — wersja koncertowa z długim tytułem",
                "Bez pośpiechu",
                "Na drugą stronę",
                "Ostatni tramwaj",
                "Dobry wieczór",
                "Dalej przed siebie"
              };
              for (int i = 0; i < titles.length; i++)
                preview.add(
                    Track.item(
                        CrowApp.obj(
                            "title",
                            titles[i],
                            "artist",
                            i % 2 == 0 ? "Studio Wrony" : "Nocna Zmiana",
                            "duration",
                            185 + i * 13,
                            "platform",
                            "Local",
                            "url",
                            "file:///ui-preview-" + i)));
              player[0].setMediaItems(preview);

            } catch (Exception error) {
              throw new RuntimeException(error);
            }
          });
      for (int i = 0; i < 5; i++) {
        final int selected = i;
        main(
            () -> {
              try {
                List<TextView> tabs = (List<TextView>) field("navigationItems");
                tabs.get(selected).performClick();
                for (int j = 0; j < tabs.size(); j++)
                  assertEquals(j == selected, tabs.get(j).isSelected());
              } catch (Exception error) {
                throw new RuntimeException(error);
              }
            });
        instrumentation.waitForIdleSync();
        snapshot(new String[] {"home", "search", "library", "queue", "settings"}[i]);
        main(
            () -> {
              try {
                View scroll = (View) field("pageScroll");
                assertTrue("Content must retain usable height", scroll.getHeight() > 200);
                View bar = (View) field("playerBar");
                assertTrue(
                    "Player fits the screen",
                    bar.getRight() <= activity.getWindow().getDecorView().getWidth());
              } catch (Exception error) {
                throw new RuntimeException(error);
              }
            });
      }
      main(
          () -> {
            try {
              List<TextView> tabs = (List<TextView>) field("navigationItems");
              tabs.get(3).performClick();
              // Menu actions validate against the queue alone (suggestions may change freely).
              Method key = MainActivity.class.getDeclaredMethod("queueOrderKey");
              key.setAccessible(true);
              Method action =
                  MainActivity.class.getDeclaredMethod(
                      "queueAction", int.class, MediaItem.class, String.class, int.class);
              action.setAccessible(true);
              MediaItem current = player[0].getMediaItemAt(0);
              MediaItem target = player[0].getMediaItemAt(3);
              String oldKey = (String) key.invoke(activity);
              action.invoke(activity, 3, target, oldKey, 1);
              assertEquals(
                  "Play-next moves the selected song", target, player[0].getMediaItemAt(1));
              assertEquals(
                  "Reordering keeps the current song", current, player[0].getCurrentMediaItem());
              int count = player[0].getMediaItemCount();
              action.invoke(activity, 3, target, oldKey, 4);
              assertEquals(
                  "Stale menu cannot delete another song", count, player[0].getMediaItemCount());
              action.invoke(activity, 1, target, (String) key.invoke(activity), 4);
              assertEquals("Remove affects one song", count - 1, player[0].getMediaItemCount());
              assertEquals(current, player[0].getCurrentMediaItem());
            } catch (Exception error) {
              throw new RuntimeException(error);
            }
          });
      main(
          () -> {
            try {
              player[0].pause();
              player[0].stop();
              player[0].setMediaItem(
                  Track.item(
                      CrowApp.obj(
                          "title",
                          "Muzyka na dobry wieczór",
                          "artist",
                          "Muzyczna Wrona",
                          "url",
                          "file:///non-playing-ui-preview")));
              Method method = MainActivity.class.getDeclaredMethod("fullPlayer");
              method.setAccessible(true);
              method.invoke(activity);
            } catch (Exception error) {
              throw new RuntimeException(error);
            }
          });
      ready(
          () ->
              ((TextView) field("expandedTitle"))
                  .getText()
                  .toString()
                  .equals("Muzyka na dobry wieczór"));
      snapshot("player");
      main(
          () ->
              player[0].setMediaItem(
                  Track.item(
                      CrowApp.obj(
                          "title",
                          "Drugi utwór",
                          "artist",
                          "Wrona",
                          "url",
                          "file:///non-playing-ui-preview-2"))));
      ready(() -> ((TextView) field("expandedTitle")).getText().toString().equals("Drugi utwór"));
      main(
          () -> {
            try {
              ((View) field("expandedRepeat")).performClick();
              ((View) field("expandedShuffle")).performClick();
            } catch (Exception error) {
              throw new RuntimeException(error);
            }
          });
      ready(
          () ->
              ((View) field("expandedShuffle")).isSelected() == player[0].getShuffleModeEnabled());
    } finally {
      main(
          () -> {
            if (player[0] != null) {
              player[0].setShuffleModeEnabled(shuffle[0]);
              player[0].setRepeatMode(repeat[0]);
              if (original.isEmpty()) player[0].clearMediaItems();
              else player[0].setMediaItems(original, index[0], position[0]);
            }
            activity.finish();
          });
    }
  }
}
