package io.github.miniu123.musiccrow;

import static org.junit.Assert.*;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

/** Explicit live-network checks; run this class separately from deterministic tests. */
@RunWith(AndroidJUnit4.class)
public class OnlineSourcesTest {
  @Test
  public void youtubeSearchAndResolve() throws Exception {
    check("YouTube Music");
  }

  @Test
  public void soundcloudSearchAndResolve() throws Exception {
    check("SoundCloud");
  }

  @Test
  public void youtubeDiscoveryFindsOriginalRecommendations() throws Exception {
    CrowApp app =
        (CrowApp)
            InstrumentationRegistry.getInstrumentation().getTargetContext().getApplicationContext();
    JSONObject found =
        new JSONObject(app.source("discover", "Kevin MacLeod", "YouTube Music", false));
    JSONObject current =
        CrowApp.obj(
            "url",
            "https://youtu.be/discovery-fixture",
            "title",
            "Carefree",
            "artist",
            "Kevin MacLeod");
    JSONObject ranked =
        new JSONObject(
            app.call(
                "recommend",
                CrowApp.obj(
                    "context",
                    new JSONArray().put(current),
                    "discoveries",
                    found.getJSONArray("tracks"))));
    JSONArray tracks = ranked.getJSONArray("tracks");
    assertTrue("Discovery returned no matching originals", tracks.length() > 0);
    for (int i = 0; i < tracks.length(); i++)
      assertFalse(
          tracks
              .getJSONObject(i)
              .optString("title")
              .toLowerCase(java.util.Locale.ROOT)
              .contains("remix"));
  }

  @Test
  public void youtubeMusicPlaylistImportLoadsBeyondFirstPage() throws Exception {
    CrowApp app =
        (CrowApp)
            InstrumentationRegistry.getInstrumentation().getTargetContext().getApplicationContext();
    // Public music fixture also used by yt-dlp's YouTube Music album tests.
    JSONObject imported =
        new JSONObject(
            app.source(
                "import_playlist",
                "https://music.youtube.com/playlist?list=OLAK5uy_l1m0thk3g31NmIIz_vMIbWtyv7eZixlH0&si=import-test"));
    JSONArray tracks = imported.getJSONArray("tracks");
    assertTrue("Import must load beyond the 30-item search preview", tracks.length() > 30);
    assertFalse(imported.getBoolean("more"));
    assertFalse(imported.getString("title").isEmpty());
    for (int i = 0; i < tracks.length(); i++) {
      assertEquals("YouTube Music", tracks.getJSONObject(i).getString("platform"));
      assertTrue(tracks.getJSONObject(i).getString("url").startsWith("https://"));
    }
  }

  private void check(String platform) throws Exception {
    CrowApp app =
        (CrowApp)
            InstrumentationRegistry.getInstrumentation().getTargetContext().getApplicationContext();
    JSONObject response = new JSONObject(app.source("search", "Kevin MacLeod Carefree", platform));
    JSONArray tracks = response.getJSONArray("tracks");
    assertTrue("No search results for " + platform, tracks.length() > 0);
    Exception last = null;
    for (int i = 0; i < Math.min(3, tracks.length()); i++) {
      try {
        JSONObject resolved =
            new JSONObject(app.source("resolve", tracks.getJSONObject(i).getString("url")));
        assertTrue(resolved.getString("url").startsWith("https://"));
        return;
      } catch (Exception error) {
        last = error;
      }
    }
    throw new AssertionError("No playable result for " + platform, last);
  }
}
