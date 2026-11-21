package io.github.miniu123.musiccrow;

import android.animation.ValueAnimator;
import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.database.Cursor;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import android.text.TextUtils;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import androidx.media3.common.*;
import androidx.media3.session.*;
import androidx.media3.session.MediaController;
import com.bumptech.glide.Glide;
import com.bumptech.glide.load.resource.drawable.DrawableTransitionOptions;
import com.google.common.util.concurrent.ListenableFuture;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.Callable;
import java.util.function.Consumer;
import org.json.*;

public final class MainActivity extends Activity {
  private CrowApp app;
  private MediaController controller;
  private ListenableFuture<MediaController> connection;
  private LinearLayout root, content, playerBar;
  private TextView titleView, nowTitle, nowArtist, time, status, suggestionStatus;
  private ImageView nowArt;
  private ImageButton play;
  private final List<TextView> navigationItems = new ArrayList<>();
  private ScrollView pageScroll;
  private Dialog playerDialog;
  private AlertDialog playlistImportDialog;
  private boolean playlistImportBusy;
  private TextView expandedTitle, expandedArtist, expandedTime;
  private ImageView expandedArt;
  private ImageButton expandedPlay, expandedShuffle, expandedRepeat;
  private SeekBar expandedSeek;
  private boolean expandedDragging;
  private String expandedArtKey = "";
  private LinearLayout playerQueue;
  // Drag & drop in the queue and in suggestions: what is being moved and from where.
  private static final int ZONE_QUEUE = 0, ZONE_SUGGESTIONS = 1;
  private int dragSource = -1;
  private int dragFrom = -1;
  private MediaItem dragItem;
  private JSONObject dragTrack;
  private View draggedRow;
  private String playerQueueKey = "";
  private static final int MUTED = 0xFFA9B0C6, SURFACE = 0xFF1C1E28;
  private SeekBar seek;
  private EditText query;
  private Spinner source;
  private boolean dragging, loaded, stopped, authorizationBusy;
  private boolean searchMore;
  private int searchOffset;
  private String homeFingerprint = "";
  private String homeLibraryKey = "";
  private LinearLayout homeSuggestions;
  private boolean homeSuggestionsEmpty, homeRefreshRequested;
  private int homeRotation;
  private int tab, generation, accent = 0xFF9672FF;
  private String playlist = "",
      pendingPlaylist = "Z telefonu",
      driveOperation = "list",
      searchQuery = "",
      searchPlatform = "YouTube Music";
  private JSONArray results = new JSONArray();
  private JSONArray artistResults = new JSONArray();
  private JSONObject artistTrack;
  private int artistOffset;
  private boolean artistMore, artistFallback;
  private String queueFingerprint = "";
  private final Handler handler = new Handler(Looper.getMainLooper());
  private final Runnable tick =
      new Runnable() {
        public void run() {
          updatePlayer();
          handler.postDelayed(this, 500);
        }
      };
  private final Player.Listener listener =
      new Player.Listener() {
        @Override
        public void onEvents(Player player, Player.Events events) {
          updatePlayer();
        }
      };
  private final BroadcastReceiver changes =
      new BroadcastReceiver() {
        public void onReceive(Context c, Intent i) {
          // Every save (including each listen added to history) broadcasts this; redraw the
          // home page only when the playlists it shows have actually changed.
          if (loaded && tab == 0 && playlist.isEmpty() && artistTrack == null
              && !libraryKey().equals(homeLibraryKey)) renderPage();
        }
      };

  @Override
  public void onCreate(Bundle saved) {
    super.onCreate(saved);
    app = (CrowApp) getApplication();
    if (saved != null) {
      tab = saved.getInt("tab");
      playlist = saved.getString("playlist", "");
      pendingPlaylist = saved.getString("pendingPlaylist", "Z telefonu");
      driveOperation = saved.getString("driveOperation", "list");
      searchQuery = saved.getString("searchQuery", "");
    }
    buildShell();
    runTask(
        () -> {
          app.call("state", new JSONObject());
          return true;
        },
        ok -> {
          loaded = true;
          buildShell();
          renderPage();
          if (PlaybackService.active != null) PlaybackService.active.refreshRecommendations(false);
        },
        this::showError);
    androidx.core.content.ContextCompat.registerReceiver(
        this,
        changes,
        new IntentFilter(CrowApp.CHANGED),
        androidx.core.content.ContextCompat.RECEIVER_NOT_EXPORTED);
  }

  @Override
  protected void onSaveInstanceState(Bundle state) {
    super.onSaveInstanceState(state);
    state.putInt("tab", tab);
    state.putString("playlist", playlist);
    state.putString("pendingPlaylist", pendingPlaylist);
    state.putString("driveOperation", driveOperation);
    state.putString("searchQuery", searchQuery);
  }

  @Override
  protected void onStart() {
    super.onStart();
    stopped = false;
    connection =
        new MediaController.Builder(
                this, new SessionToken(this, new ComponentName(this, PlaybackService.class)))
            .buildAsync();
    final ListenableFuture<MediaController> pending = connection;
    pending.addListener(
        () -> {
          if (connection != pending) return;
          try {
            controller = pending.get();
            controller.addListener(listener);
            updatePlayer();
            if (loaded && PlaybackService.active != null)
              PlaybackService.active.refreshRecommendations(false);
          } catch (Exception e) {
            showError(tr("Odtwarzacz niedostępny", "Player unavailable"));
          }
        },
        command -> handler.post(command));
    handler.post(tick);
  }

  @Override
  protected void onStop() {
    handler.removeCallbacks(tick);
    stopped = true;
    if (controller != null) controller.removeListener(listener);
    if (connection != null) MediaController.releaseFuture(connection);
    connection = null;
    controller = null;
    super.onStop();
  }

  @Override
  protected void onDestroy() {
    if (playerDialog != null) playerDialog.dismiss();
    if (playlistImportDialog != null) playlistImportDialog.dismiss();
    unregisterReceiver(changes);
    handler.removeCallbacksAndMessages(null);
    super.onDestroy();
  }

  @Override
  public void onBackPressed() {
    if (artistTrack != null) {
      artistTrack = null;
      tab = 1;
      renderPage();
    } else if (!playlist.isEmpty()) {
      playlist = "";
      tab = 2;
      renderPage();
    } else if (tab != 0) {
      tab = 0;
      renderPage();
    } else super.onBackPressed();
  }

  private boolean fullscreenEnabled() {
    // The full-screen switch was removed; status and navigation bars stay visible.
    return false;
  }

  private void configureScreen(Window window) {
    androidx.core.view.WindowCompat.setDecorFitsSystemWindows(window, false);
    window.setStatusBarColor(Color.TRANSPARENT);
    window.setNavigationBarColor(Color.TRANSPARENT);
    if (Build.VERSION.SDK_INT >= 29) {
      window.setNavigationBarContrastEnforced(false);
      window.setStatusBarContrastEnforced(false);
    }
    if (Build.VERSION.SDK_INT >= 28) {
      WindowManager.LayoutParams attrs = window.getAttributes();
      attrs.layoutInDisplayCutoutMode =
          WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
      window.setAttributes(attrs);
    }
    androidx.core.view.WindowInsetsControllerCompat bars =
        androidx.core.view.WindowCompat.getInsetsController(window, window.getDecorView());
    bars.setAppearanceLightStatusBars(false);
    bars.setAppearanceLightNavigationBars(false);
    bars.setSystemBarsBehavior(
        androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    if (fullscreenEnabled()) bars.hide(androidx.core.view.WindowInsetsCompat.Type.systemBars());
    else bars.show(androidx.core.view.WindowInsetsCompat.Type.systemBars());
  }

  private void applyScreenInsets(View target, int horizontal, int vertical) {
    androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(
        target,
        (view, insets) -> {
          int types = androidx.core.view.WindowInsetsCompat.Type.displayCutout();
          if (!fullscreenEnabled())
            types |= androidx.core.view.WindowInsetsCompat.Type.systemBars();
          androidx.core.graphics.Insets safe = insets.getInsets(types);
          int keyboard = insets.getInsets(androidx.core.view.WindowInsetsCompat.Type.ime()).bottom;
          view.setPadding(
              dp(horizontal) + safe.left,
              dp(vertical) + safe.top,
              dp(horizontal) + safe.right,
              dp(vertical) + Math.max(safe.bottom, keyboard));
          return insets;
        });
  }

  @Override
  public void onWindowFocusChanged(boolean focused) {
    super.onWindowFocusChanged(focused);
    if (focused) configureScreen(getWindow());
  }

  private boolean english() {
    return "en".equals(app.settings().optString("LANGUAGE"));
  }

  private String tr(String pl, String en) {
    return english() ? en : pl;
  }

  private void buildShell() {
    try {
      accent = Color.parseColor(app.settings().optString("ACCENT_COLOR", "#9672FF"));
    } catch (Exception ignored) {
    }
    navigationItems.clear();
    artKey = "__reset__";
    root = column();
    root.setBackgroundColor(themeColor("MAIN_BG_COLOR", 0xFF10131F));
    root.setPadding(dp(16), 0, dp(16), 0);
    configureScreen(getWindow());
    applyScreenInsets(root, 16, 4);
    setContentView(root);
    root.requestApplyInsets();
    LinearLayout brand = row();
    ImageView logo = new ImageView(this);
    logo.setImageResource(R.drawable.music_crow);
    brand.addView(logo, new LinearLayout.LayoutParams(dp(26), dp(26)));
    TextView wordmark = text("MUSIC CROW", 12, MUTED);
    wordmark.setTypeface(null, Typeface.BOLD);
    wordmark.setLetterSpacing(0.16f);
    wordmark.setPadding(dp(10), 0, 0, 0);
    brand.addView(wordmark);
    brand.setPadding(0, dp(4), 0, dp(8));
    root.addView(brand);
    titleView = text(tr("Twoja muzyka, blisko.", "Your music, always close."), 24, Color.WHITE);
    titleView.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    titleView.setMaxLines(2);
    titleView.setEllipsize(TextUtils.TruncateAt.END);
    titleView.setPadding(0, dp(2), 0, dp(12));
    root.addView(titleView);
    if (getResources().getConfiguration().screenHeightDp < 500) {
      brand.setVisibility(View.GONE);
      titleView.setTextSize(22);
      titleView.setPadding(0, 0, 0, dp(8));
    }
    ScrollView scroll = new ScrollView(this);
    pageScroll = scroll;
    scroll.setVerticalScrollBarEnabled(false);
    scroll.setFillViewport(true);
    content = column();
    content.setFocusableInTouchMode(true);
    content.setPadding(0, 0, 0, dp(20));
    scroll.addView(content);
    root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    if (!loaded)
      content.addView(text(tr("Otwieranie biblioteki…", "Opening library…"), 16, 0xFFA3ABC5));
    buildPlayer();
    LinearLayout navigation = row();
    String[] labels = {
      tr("Start", "Home"),
      tr("Szukaj", "Search"),
      tr("Playlisty", "Library"),
      tr("Kolejka", "Queue"),
      tr("Ustawienia", "Settings")
    };
    int[] icons = {
      R.drawable.ic_home,
      R.drawable.ic_search,
      R.drawable.ic_library,
      R.drawable.ic_queue,
      R.drawable.ic_settings
    };
    navigation.setPadding(0, dp(8), 0, 0);
    for (int i = 0; i < labels.length; i++) {
      final int dest = i;
      TextView item = text(labels[i], 10, MUTED);
      item.setGravity(Gravity.CENTER);
      item.setMaxLines(1);
      item.setCompoundDrawablePadding(dp(4));
      Drawable icon = getDrawable(icons[i]).mutate();
      icon.setBounds(0, 0, dp(22), dp(22));
      item.setCompoundDrawables(null, icon, null, null);
      item.setBackground(ripple(Color.TRANSPARENT, 16));
      item.setContentDescription(labels[i]);
      pressFeedback(item);
      item.setOnClickListener(
          v -> {
            if (tab == 1 && artistTrack == null && query != null) {
              searchQuery = query.getText().toString();
              searchPlatform = String.valueOf(source.getSelectedItem());
            }
            tab = dest;
            playlist = "";
            artistTrack = null;
            renderPage();
            pageScroll.scrollTo(0, 0);
          });
      navigationItems.add(item);
      navigation.addView(item, new LinearLayout.LayoutParams(0, dp(56), 1));
    }
    root.addView(navigation);
  }

  private void buildPlayer() {
    playerBar = column();
    playerBar.setPadding(dp(12), dp(10), dp(8), dp(4));
    playerBar.setBackground(background(themeColor("PLAYER_BAR_BG", 0xFF20263B)));
    LinearLayout metadata = row();
    nowArt = art("", false);
    metadata.addView(nowArt, new LinearLayout.LayoutParams(dp(48), dp(48)));
    LinearLayout names = column();
    names.setPadding(dp(12), 0, dp(4), 0);
    nowTitle = text(tr("Wybierz coś do słuchania", "Pick something to play"), 14, Color.WHITE);
    nowTitle.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    nowTitle.setMaxLines(1);
    nowArtist = text(tr("Muzyka czeka na Ciebie", "Your music is waiting"), 12, MUTED);
    nowArtist.setMaxLines(1);
    names.addView(nowTitle);
    names.addView(nowArtist);
    metadata.addView(names, new LinearLayout.LayoutParams(0, -2, 1));
    names.setOnClickListener(v -> fullPlayer());
    nowArt.setOnClickListener(v -> fullPlayer());
    play = iconButton(R.drawable.ic_play, tr("Odtwórz", "Play"), this::togglePlayback);
    play.setBackground(ripple(accent, 24));
    play.setImageTintList(ColorStateList.valueOf(0xFF10131F));
    metadata.addView(play, new LinearLayout.LayoutParams(dp(48), dp(48)));
    ImageButton next =
        iconButton(R.drawable.ic_next, tr("Następny utwór", "Next track"), this::nextTrack);
    metadata.addView(next, new LinearLayout.LayoutParams(dp(48), dp(48)));
    playerBar.addView(metadata);
    seek = playbackSeek(false);
    playerBar.addView(seek, new LinearLayout.LayoutParams(-1, dp(28)));
    LinearLayout lower = row();
    time = text("0:00 / 0:00", 10, MUTED);
    lower.addView(time, new LinearLayout.LayoutParams(0, -2, 1));
    TextView expandHint = text(tr("Rozwiń odtwarzacz", "Expand player"), 10, MUTED);
    expandHint.setMaxLines(1);
    expandHint.setOnClickListener(v -> fullPlayer());
    lower.addView(expandHint);
    playerBar.addView(lower);
    root.addView(playerBar);
  }

  private void nextTrack() {
    if (controller != null) controller.seekToNextMediaItem();
  }

  private void previousTrack() {
    if (controller != null) {
      editQueue();
      controller.seekToPrevious();
    }
  }

  private void toggleShuffle() {
    if (controller != null) controller.setShuffleModeEnabled(!controller.getShuffleModeEnabled());
  }

  private void toggleRepeat() {
    if (controller != null) controller.setRepeatMode((controller.getRepeatMode() + 1) % 3);
  }

  private SeekBar playbackSeek(boolean expanded) {
    SeekBar bar = new SeekBar(this);
    bar.setMax(1000);
    tintSeek(bar);
    bar.setContentDescription(tr("Pozycja odtwarzania", "Playback position"));
    bar.setOnSeekBarChangeListener(
        new SeekBar.OnSeekBarChangeListener() {
          public void onStartTrackingTouch(SeekBar b) {
            if (expanded) expandedDragging = true;
            else dragging = true;
          }

          public void onProgressChanged(SeekBar b, int p, boolean user) {}

          public void onStopTrackingTouch(SeekBar b) {
            if (controller != null
                && controller.getDuration() > 0
                && controller.isCurrentMediaItemSeekable()) {
              editQueue();
              controller.seekTo(controller.getDuration() * b.getProgress() / 1000);
            }
            if (expanded) expandedDragging = false;
            else dragging = false;
          }
        });
    return bar;
  }

  private void updateNavigation() {
    for (int i = 0; i < navigationItems.size(); i++) {
      TextView item = navigationItems.get(i);
      int color = i == tab ? accent : MUTED;
      item.setTextColor(color);
      item.getCompoundDrawables()[1].setTint(color);
      item.setSelected(i == tab);
      item.setBackground(
          ripple(
              i == tab
                  ? blend(accent, themeColor("MAIN_BG_COLOR", 0xFF10131F), 0.12f)
                  : Color.TRANSPARENT,
              12));
      item.setTypeface(null, i == tab ? Typeface.BOLD : Typeface.NORMAL);
    }
  }

  private void renderPage() {
    if (!loaded) return;
    generation++;
    updateNavigation();
    content.removeAllViews();
    content.requestFocus();
    animatePageEntrance();
    queueFingerprint = "";
    if (artistTrack != null) {
      renderArtist();
      return;
    }
    if (!playlist.isEmpty()) {
      renderPlaylist();
      return;
    }
    switch (tab) {
      case 0:
        renderHome();
        break;
      case 1:
        renderSearch();
        break;
      case 2:
        renderLibrary();
        break;
      case 3:
        renderQueue();
        break;
      default:
        renderSettings();
    }
  }

  private JSONObject playlists() {
    JSONObject p = app.state.optJSONObject("playlists");
    return p == null ? new JSONObject() : p;
  }

  private List<String> playlistNames() {
    List<String> names = new ArrayList<>();
    Iterator<String> keys = playlists().keys();
    while (keys.hasNext()) names.add(keys.next());
    Collections.sort(names, String.CASE_INSENSITIVE_ORDER);
    return names;
  }

  private void renderHome() {
    titleView.setText(tr("Dobrze Cię słyszeć.", "Good to hear you."));
    LinearLayout hero = card();
    hero.setPadding(dp(20), dp(20), dp(20), dp(18));
    GradientDrawable glow =
        new GradientDrawable(
            GradientDrawable.Orientation.TL_BR,
            new int[] {blend(accent, 0xFF10131F, 0.35f), 0xFF1B2032});
    glow.setCornerRadius(dp(24));
    hero.setBackground(glow);
    TextView eyebrow = text(tr("TWOJE MIEJSCE NA MUZYKĘ", "YOUR SPACE FOR MUSIC"), 10, 0xFFD4C9FF);
    eyebrow.setLetterSpacing(0.12f);
    hero.addView(eyebrow);
    hero.addView(
        text(tr("Wszystko, czego słuchasz.", "Everything you listen to."), 22, Color.WHITE));
    hero.addView(
        text(
            tr(
                "Twoje playlisty, odkrycia i ulubione brzmienia.",
                "Your playlists, discoveries and favourite sounds."),
            14,
            0xFFA3ABC5));
    hero.addView(
        primaryButton(
            tr("Znajdź muzykę", "Find music"),
            () -> {
              tab = 1;
              renderPage();
            }));
    content.addView(hero);
    section(tr("Twoje playlisty", "Your playlists"));
    homeLibraryKey = libraryKey();
    List<String> homeLists = playlistNames();
    for (String name : homeLists.subList(0, Math.min(3, homeLists.size()))) playlistCard(name);
    if (homeLists.size() > 3)
      content.addView(
          button(
              tr("Zobacz wszystkie playlisty", "See all playlists"),
              () -> {
                tab = 2;
                renderPage();
                pageScroll.scrollTo(0, 0);
              }));
    if (playlistNames().isEmpty())
      content.addView(
          button(
              tr("+ Utwórz pierwszą playlistę", "+ Create your first playlist"),
              () -> createPlaylist(null)));
    section(tr("Polecane dla Ciebie", "Recommended for you"));
    homeSuggestions = column();
    content.addView(homeSuggestions);
    loadHomeSuggestions();
    content.addView(
        button(
            tr("Odkryj podobną muzykę", "Discover similar music"),
            () -> {
              homeRotation++;
              homeRefreshRequested = true; // show new discoveries once they have arrived
              loadHomeSuggestions();
              if (PlaybackService.active != null) {
                PlaybackService.active.refreshRecommendations(true);
                toast(tr("Szukam nowej muzyki…", "Finding new music…"));
              }
            }));
  }

  /**
   * Home suggestions come from listening history and playlists, not from the song that is
   * playing right now, and stay put while new discoveries arrive in the background.
   */
  private void loadHomeSuggestions() {
    LinearLayout target = homeSuggestions;
    if (target == null) return;
    int request = generation;
    homeFingerprint = recommendationKey();
    JSONArray discoveries = new JSONArray();
    for (JSONObject t : PlaybackService.recommendations) discoveries.put(t);
    JSONArray excluded = new JSONArray();
    if (controller != null)
      for (int i = 0; i < controller.getMediaItemCount(); i++)
        excluded.put(Track.json(controller.getMediaItemAt(i)));
    JSONObject args =
        CrowApp.obj(
            "context", new JSONArray(),
            "discoveries", discoveries,
            "excluded", excluded,
            "rotation", homeRotation);
    runTask(
        () -> new JSONObject(app.call("recommend", args)),
        data -> {
          if (generation != request || target != homeSuggestions) return;
          JSONArray tracks = data.optJSONArray("tracks");
          target.removeAllViews();
          homeSuggestionsEmpty = tracks == null || tracks.length() == 0;
          if (homeSuggestionsEmpty) target.addView(text(suggestionMessage(), 14, 0xFFA3ABC5));
          else trackRows(target, first(tracks, 8), "");
        },
        this::showError);
  }

  /** What the home page shows of the library: playlist names, sizes and covers. */
  private String libraryKey() {
    StringBuilder key = new StringBuilder();
    JSONObject all = playlists();
    for (String name : playlistNames()) {
      JSONObject p = all.optJSONObject(name);
      JSONArray tracks = p == null ? null : p.optJSONArray("tracks");
      key.append(name).append('|').append(tracks == null ? 0 : tracks.length()).append('|')
          .append(p == null ? 0 : p.optString("cover").hashCode()).append('\n');
    }
    return key.toString();
  }

  private void renderLibrary() {
    titleView.setText(tr("Twoje playlisty", "Your playlists"));
    content.addView(
        text(
            tr("Twoja kolekcja, zawsze pod ręką.", "Your collection, always with you."),
            14,
            MUTED));
    content.addView(
        primaryButton(tr("+ Nowa playlista", "+ New playlist"), () -> createPlaylist(null)));
    Button importMusic =
        button(
            tr("Importuj z YouTube Music", "Import from YouTube Music"),
            () -> showPlaylistImport(""));
    importMusic.setTag("import-youtube-music");
    content.addView(importMusic);
    content.addView(
        button(
            tr("+ Pliki z telefonu", "+ Files from phone"),
            () -> {
              pendingPlaylist = tr("Z telefonu", "From phone");
              openAudio();
            }));
    if (playlistNames().isEmpty())
      emptyState(
          tr("Pierwsza playlista?", "Your first playlist?"),
          tr(
              "Zapisuj odkrycia z wyszukiwarki albo dodaj muzykę z telefonu.",
              "Save discoveries from search or add music from your phone."));
    for (String name : playlistNames()) playlistCard(name);
  }

  private void playlistCard(String name) {
    JSONObject p = playlists().optJSONObject(name);
    if (p == null) return;
    LinearLayout card = card();
    LinearLayout line = row();
    ImageView art = art(p.optString("cover"), true);
    line.addView(art, new LinearLayout.LayoutParams(dp(64), dp(64)));
    LinearLayout words = column();
    words.setPadding(dp(12), 0, 0, 0);
    TextView label = text(name, 17, Color.WHITE);
    label.setMaxLines(2);
    label.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    words.addView(label);
    words.addView(text(trackCount(p.optJSONArray("tracks").length()), 13, 0xFFA3ABC5));
    line.addView(words, new LinearLayout.LayoutParams(0, -2, 1));
    JSONArray cardTracks = p.optJSONArray("tracks");
    if (cardTracks != null && cardTracks.length() > 0) {
      ImageButton shuffle =
          iconButton(
              R.drawable.ic_shuffle,
              tr("Odtwórz losowo: ", "Shuffle play: ") + name,
              () -> playShuffled(cardTracks));
      shuffle.setImageTintList(ColorStateList.valueOf(accent));
      line.addView(shuffle, new LinearLayout.LayoutParams(dp(48), dp(48)));
    }
    TextView arrow = text("›", 26, MUTED);
    arrow.setPadding(dp(8), 0, dp(2), 0);
    line.addView(arrow);
    card.addView(line);
    card.setOnClickListener(
        v -> {
          playlist = name;
          tab = 2;
          renderPage();
          pageScroll.scrollTo(0, 0);
        });
    pressFeedback(card);
    content.addView(card);
  }

  private void renderPlaylist() {
    JSONObject p = playlists().optJSONObject(playlist);
    if (p == null) {
      playlist = "";
      renderLibrary();
      return;
    }
    titleView.setText(playlist);
    JSONArray tracks = p.optJSONArray("tracks");
    ImageView cover = art(p.optString("cover"), true);
    LinearLayout.LayoutParams coverParams = new LinearLayout.LayoutParams(dp(176), dp(176));
    coverParams.gravity = Gravity.CENTER_HORIZONTAL;
    coverParams.setMargins(0, dp(4), 0, dp(12));
    content.addView(cover, coverParams);
    content.addView(text(trackCount(tracks.length()), 13, MUTED));
    cover.setOnClickListener(
        v -> {
          pendingPlaylist = playlist;
          openDocument("image/*", 32);
        });
    LinearLayout actions = row();
    addWeighted(actions, primaryButton(tr("▶ Odtwórz", "▶ Play"), () -> playInOrder(tracks)));
    Button shuffled = button(tr("Losowo", "Shuffle"), () -> playShuffled(tracks));
    shuffled.setTag("playlist-shuffle");
    shuffled.setCompoundDrawablesRelativeWithIntrinsicBounds(R.drawable.ic_shuffle, 0, 0, 0);
    shuffled.setCompoundDrawableTintList(ColorStateList.valueOf(accent));
    shuffled.setCompoundDrawablePadding(dp(6));
    addWeighted(actions, shuffled);
    content.addView(actions);
    content.addView(button(tr("Opcje playlisty", "Playlist options"), () -> playlistOptions()));
    content.addView(
        button(
            tr("+ Dodaj utwory", "+ Add tracks"),
            () ->
                new AlertDialog.Builder(this)
                    .setItems(
                        new String[] {
                          tr("Wyszukaj online", "Search online"),
                          tr("Pliki z telefonu", "Files from phone")
                        },
                        (d, i) -> {
                          if (i == 0) {
                            playlist = "";
                            tab = 1;
                            renderPage();
                          } else {
                            pendingPlaylist = playlist;
                            openAudio();
                          }
                        })
                    .show()));
    if (tracks.length() == 0)
      emptyState(
          tr("Tu zaczyna się Twoja playlista", "Your playlist starts here"),
          tr(
              "Dodaj pierwszy utwór, żeby zacząć słuchać.",
              "Add your first track to start listening."));
    trackRows(content, tracks, playlist);
  }

  private void playlistOptions() {
    String name = playlist;
    new AlertDialog.Builder(this)
        .setTitle(name)
        .setItems(
            new String[] {
              tr("Zmień nazwę", "Rename"),
              tr("Zmień okładkę", "Change cover"),
              tr("Usuń playlistę", "Delete playlist")
            },
            (d, i) -> {
              if (i == 0)
                prompt(
                    tr("Nowa nazwa", "New name"),
                    name,
                    value ->
                        mutate(
                            "rename",
                            CrowApp.obj("name", name, "new", value),
                            () -> {
                              playlist = value.trim();
                              renderPage();
                            }));
              if (i == 1) {
                pendingPlaylist = name;
                openDocument("image/*", 32);
              }
              if (i == 2)
                confirm(
                    tr("Usunąć playlistę?", "Delete playlist?"),
                    name,
                    () ->
                        mutate(
                            "delete",
                            CrowApp.obj("name", name),
                            () -> {
                              playlist = "";
                              renderPage();
                            }));
            })
        .show();
  }

  private void createPlaylist(JSONObject track) {
    prompt(
        tr("Nazwa playlisty", "Playlist name"),
        "",
        name ->
            mutate(
                "create",
                CrowApp.obj("name", name),
                () -> {
                  if (track != null)
                    mutate(
                        "add",
                        CrowApp.obj("name", name.trim(), "tracks", new JSONArray().put(track)),
                        this::renderPage);
                  else renderPage();
                }));
  }

  private void saveToPlaylist(JSONObject track) {
    List<String> names = playlistNames();
    List<String> labels = new ArrayList<>(names);
    labels.add(tr("+ Nowa playlista", "+ New playlist"));
    new AlertDialog.Builder(this)
        .setTitle(tr("Dodaj do playlisty", "Add to playlist"))
        .setItems(
            labels.toArray(new String[0]),
            (d, i) -> {
              if (i == names.size()) createPlaylist(track);
              else
                mutate(
                    "add",
                    CrowApp.obj("name", names.get(i), "tracks", new JSONArray().put(track)),
                    () -> toast(tr("Zapisano", "Saved")));
            })
        .show();
  }

  private void renderSearch() {
    titleView.setText(tr("Znajdź swoje brzmienie.", "Find your sound."));
    query = new EditText(this);
    query.setSingleLine(true);
    query.setTextColor(Color.WHITE);
    query.setHintTextColor(0xFFA3ABC5);
    query.setHint(tr("Utwór, artysta lub link do playlisty", "Track, artist or playlist link"));
    query.setText(searchQuery);
    query.setTextSize(16);
    query.setPadding(dp(16), dp(12), dp(16), dp(12));
    query.setBackground(background(SURFACE));
    query.setMinHeight(dp(56));
    query.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH);
    query.setOnEditorActionListener(
        (v, actionId, event) -> {
          if (actionId == android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH) {
            search();
            return true;
          }
          return false;
        });
    content.addView(query);
    source = new Spinner(this);
    source.setAdapter(
        new ArrayAdapter<>(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            new String[] {"YouTube Music", "SoundCloud"}));
    source.setSelection("SoundCloud".equals(searchPlatform) ? 1 : 0);
    source.setMinimumHeight(dp(52));
    content.addView(source);
    content.addView(primaryButton(tr("Szukaj", "Search"), this::search));
    status = text("", 14, 0xFFA3ABC5);
    content.addView(status);
    if (results.length() > 0) {
      content.addView(
          button(
              tr("Zapisz wczytane utwory jako playlistę", "Save loaded tracks as playlist"),
              () ->
                  prompt(
                      tr("Nazwa playlisty", "Playlist name"),
                      searchQuery,
                      value ->
                          mutate(
                              "add",
                              CrowApp.obj("name", value, "tracks", results),
                              () -> toast(tr("Zapisano playlistę", "Playlist saved"))))));
      trackRows(content, results, "");
    }
    if (searchMore)
      content.addView(
          button(
              tr("Wczytaj dalszą część playlisty", "Load more of the playlist"),
              this::loadMoreSearch));
    if (searchQuery.startsWith("https://"))
      content.addView(
          button(
              tr("Importuj całą playlistę z linku…", "Import full playlist from link…"),
              this::importFullPlaylist));
  }

  private void search() {
    searchQuery = query.getText().toString().trim();
    searchPlatform = String.valueOf(source.getSelectedItem());
    if (searchQuery.isEmpty()) return;
    ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
        .hideSoftInputFromWindow(query.getWindowToken(), 0);
    query.clearFocus();
    int request = ++generation;
    status.setText(tr("Szukam…", "Searching…"));
    String requestedQuery = searchQuery, requestedPlatform = searchPlatform;
    runTask(
        () -> new JSONObject(app.source("search", requestedQuery, requestedPlatform)),
        data -> {
          if (request != generation) return;
          searchMore = data.optBoolean("more") && searchQuery.startsWith("https://");
          searchOffset = 30;
          results = data.optJSONArray("tracks");
          if (results == null) results = new JSONArray();
          renderPage();
          if (results.length() == 0) status.setText(tr("Brak wyników", "No results"));
        },
        message -> {
          if (request == generation) status.setText(message);
        });
  }

  private void openArtist(JSONObject track) {
    artistTrack = track;
    artistResults = new JSONArray();
    artistOffset = 0;
    artistMore = false;
    artistFallback = false;
    renderPage();
    loadArtist();
  }

  private void loadArtist() {
    int request = generation;
    JSONObject track = artistTrack;
    int offset = artistOffset;
    status.setText(tr("Wczytywanie kanału…", "Loading channel…"));
    runTask(
        () -> new JSONObject(app.source("browse", track.toString(), offset)),
        data -> {
          if (request != generation) return;
          JSONArray batch = data.optJSONArray("tracks");
          for (int i = 0; batch != null && i < batch.length(); i++)
            artistResults.put(batch.optJSONObject(i));
          artistOffset += 30;
          artistMore = data.optBoolean("more");
          artistFallback = data.optBoolean("fallback");
          renderPage();
        },
        message -> {
          if (request == generation) status.setText(message);
        });
  }

  private void renderArtist() {
    titleView.setText(Track.artist(artistTrack));
    content.addView(
        button(
            tr("← Wróć", "← Back"),
            () -> {
              artistTrack = null;
              renderPage();
            }));
    status =
        text(
            artistFallback
                ? tr(
                    "Wyniki wyszukiwania artysty — kanał nieznany",
                    "Artist search results — channel unknown")
                : tr("Utwory z kanału", "Tracks from channel"),
            14,
            0xFFA3ABC5);
    content.addView(status);
    trackRows(content, artistResults, "");
    if (artistMore && !artistFallback)
      content.addView(button(tr("Pokaż więcej", "Show more"), this::loadArtist));
  }

  private void trackRows(LinearLayout into, JSONArray tracks, String listName) {
    LinearLayout list = column();
    into.addView(list);
    appendRows(list, tracks, listName, 0);
  }

  private void appendRows(LinearLayout into, JSONArray tracks, String name, int offset) {
    int end = Math.min(tracks.length(), offset + 50);
    for (int i = offset; i < end; i++) {
      JSONObject track = tracks.optJSONObject(i);
      if (track != null) into.addView(trackRow(track, tracks, i, name));
    }
    if (end < tracks.length()) {
      Button more = button(tr("Pokaż kolejne utwory", "Show more tracks"), () -> {});
      more.setOnClickListener(
          v -> {
            into.removeView(more);
            appendRows(into, tracks, name, end);
          });
      into.addView(more);
    }
  }

  private void loadMoreSearch() {
    int request = ++generation;
    String url = searchQuery;
    int offset = searchOffset;
    status.setText(tr("Wczytywanie…", "Loading…"));
    runTask(
        () -> new JSONObject(app.source("page", url, offset)),
        data -> {
          if (request != generation) return;
          JSONArray batch = data.optJSONArray("tracks");
          Set<String> seen = new HashSet<>();
          for (int i = 0; i < results.length(); i++)
            seen.add(results.optJSONObject(i).optString("url"));
          for (int i = 0; batch != null && i < batch.length(); i++) {
            JSONObject t = batch.optJSONObject(i);
            if (t != null && seen.add(t.optString("url"))) results.put(t);
          }
          searchOffset += 30;
          searchMore = data.optBoolean("more");
          renderPage();
        },
        message -> {
          if (request == generation) status.setText(message);
        });
  }

  private void importFullPlaylist() {
    showPlaylistImport(searchQuery);
  }

  private void showPlaylistImport(String initialUrl) {
    if (playlistImportBusy) {
      toast(tr("Importowanie już trwa…", "Import already in progress…"));
      return;
    }
    LinearLayout form = column();
    form.setPadding(dp(24), dp(8), dp(24), dp(8));
    form.addView(
        text(
            tr(
                "W YouTube Music otwórz playlistę → Udostępnij → Kopiuj link. Playlista musi być"
                    + " publiczna lub niepubliczna (dostępna z linku).",
                "In YouTube Music open a playlist → Share → Copy link. Use a public or unlisted"
                    + " playlist."),
            14,
            MUTED));
    EditText link = new EditText(this);
    link.setTag("playlist-import-url");
    link.setHint("https://music.youtube.com/playlist?list=…");
    link.setInputType(
        android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
    link.setSingleLine(true);
    link.setText(initialUrl);
    form.addView(link);
    AlertDialog dialog =
        new AlertDialog.Builder(this)
            .setTitle(tr("Importuj playlistę", "Import playlist"))
            .setView(form)
            .setNegativeButton(tr("Anuluj", "Cancel"), null)
            .setPositiveButton(tr("Wczytaj playlistę", "Load playlist"), null)
            .create();
    playlistImportDialog = dialog;
    dialog.setOnShowListener(
        ignored ->
            dialog
                .getButton(AlertDialog.BUTTON_POSITIVE)
                .setOnClickListener(
                    v -> {
                      String url = link.getText().toString().trim();
                      if (url.isEmpty()) {
                        link.setError(tr("Wklej link do playlisty", "Paste a playlist link"));
                        return;
                      }
                      dialog.dismiss();
                      loadPlaylistImport(url);
                    }));
    dialog.show();
  }

  private void loadPlaylistImport(String url) {
    if (playlistImportBusy) return;
    playlistImportBusy = true;
    LinearLayout progress = column();
    progress.setPadding(dp(24), dp(16), dp(24), dp(16));
    progress.addView(new ProgressBar(this));
    progress.addView(
        text(
            tr(
                "Pobieram listę utworów… Duże playlisty mogą wymagać chwili.",
                "Loading tracks… Large playlists may take a moment."),
            14,
            MUTED));
    AlertDialog dialog =
        new AlertDialog.Builder(this)
            .setTitle(tr("Wczytywanie playlisty", "Loading playlist"))
            .setView(progress)
            .setNegativeButton(tr("Anuluj", "Cancel"), (d, which) -> {})
            .create();
    boolean[] cancelled = {false};
    dialog.setOnDismissListener(d -> cancelled[0] = true);
    playlistImportDialog = dialog;
    dialog.show();
    runTask(
        () -> new JSONObject(app.source("import_playlist", url)),
        imported -> {
          playlistImportBusy = false;
          if (cancelled[0]) return;
          dialog.dismiss();
          previewPlaylistImport(imported);
        },
        error -> {
          playlistImportBusy = false;
          if (cancelled[0]) return;
          dialog.dismiss();
          showError(error);
        });
  }

  private void previewPlaylistImport(JSONObject imported) {
    JSONArray tracks = imported.optJSONArray("tracks");
    if (tracks == null || tracks.length() == 0) {
      showError(tr("Brak dostępnych utworów", "No available tracks"));
      return;
    }
    String base =
        imported
            .optString("title", "YouTube Music")
            .replace('/', ' ')
            .replace('\\', ' ')
            .replaceAll("\\p{Cntrl}", " ")
            .trim();
    if (base.isEmpty() || base.equals(".") || base.equals("..")) base = "YouTube Music";
    if (base.length() > 160) base = base.substring(0, 160);
    String proposed = base;
    for (int n = 2; playlists().has(proposed); n++) proposed = base + " (" + n + ")";
    LinearLayout form = column();
    form.setPadding(dp(24), dp(8), dp(24), dp(8));
    String summary = trackCount(tracks.length());
    int skipped = imported.optInt("skipped");
    if (skipped > 0)
      summary += tr(" • Niedostępne pominięte: ", " • Unavailable skipped: ") + skipped;
    form.addView(text(summary, 14, MUTED));
    EditText name = new EditText(this);
    name.setTag("playlist-import-name");
    name.setSingleLine(true);
    name.setHint(tr("Nazwa nowej playlisty", "New playlist name"));
    name.setText(proposed);
    form.addView(name);
    AlertDialog dialog =
        new AlertDialog.Builder(this)
            .setTitle(tr("Zapisz playlistę", "Save playlist"))
            .setView(form)
            .setNegativeButton(tr("Anuluj", "Cancel"), null)
            .setPositiveButton(tr("Importuj", "Import"), null)
            .create();
    playlistImportDialog = dialog;
    dialog.setOnShowListener(
        ignored ->
            dialog
                .getButton(AlertDialog.BUTTON_POSITIVE)
                .setOnClickListener(
                    v -> {
                      String destination = name.getText().toString().trim();
                      if (destination.isEmpty()) {
                        name.setError(tr("Wpisz nazwę", "Enter a name"));
                        return;
                      }
                      if (playlists().has(destination)) {
                        name.setError(tr("Ta nazwa już istnieje", "This name already exists"));
                        return;
                      }
                      if (playlistImportBusy) return;
                      playlistImportBusy = true;
                      dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                      runTask(
                          () ->
                              app.call(
                                  "add",
                                  CrowApp.obj(
                                      "name", destination, "tracks", tracks, "new_only", true)),
                          saved -> {
                            playlistImportBusy = false;
                            dialog.dismiss();
                            playlist = destination;
                            artistTrack = null;
                            tab = 2;
                            renderPage();
                            toast(tr("Zaimportowano: ", "Imported: ") + tracks.length());
                          },
                          error -> {
                            playlistImportBusy = false;
                            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                            name.setError(error);
                          });
                    }));
    dialog.show();
  }

  private JSONArray first(JSONArray list, int count) {
    JSONArray result = new JSONArray();
    Set<String> seen = new HashSet<>();
    Map<String, Integer> artists = new HashMap<>();
    for (int i = 0; i < list.length() && result.length() < count; i++) {
      JSONObject track = list.optJSONObject(i);
      if (track == null) continue;
      String artist = Track.artist(track);
      int total = artists.containsKey(artist) ? artists.get(artist) : 0;
      if (seen.add(track.optString("url")) && total < 2) {
        result.put(track);
        artists.put(artist, total + 1);
      }
    }
    return result;
  }

  private String trackCount(int count) {
    if (english()) return count + (count == 1 ? " track" : " tracks");
    return count
        + (count == 1
            ? " utwór"
            : count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14)
                ? " utwory"
                : " utworów");
  }

  private String recommendationKey() {
    StringBuilder key = new StringBuilder();
    key.append(PlaybackService.recommendationLoading).append(PlaybackService.recommendationFailed);
    for (JSONObject track : PlaybackService.recommendations) key.append(track.optString("url"));
    return key.toString();
  }

  private int themeColor(String key, int fallback) {
    String value = app.settings().optString(key);
    try {
      if (value.startsWith("rgba(")) {
        String[] components = value.substring(5, value.length() - 1).split(",");
        return Color.argb(
            (int) (255 * Float.parseFloat(components[3].trim())),
            Integer.parseInt(components[0].trim()),
            Integer.parseInt(components[1].trim()),
            Integer.parseInt(components[2].trim()));
      }
      return Color.parseColor(value);
    } catch (Exception e) {
      return fallback;
    }
  }

  private View trackRow(JSONObject track, JSONArray group, int index, String listName) {
    LinearLayout row = musicRow(false);
    ImageView thumbnail = art(track.optString("thumbnail_url"), false);
    row.addView(thumbnail, new LinearLayout.LayoutParams(dp(48), dp(48)));
    LinearLayout labels = column();
    labels.setPadding(dp(10), 0, dp(4), 0);
    TextView title = text(track.optString("title"), 15, Color.WHITE);
    title.setMaxLines(2);
    labels.addView(title);
    TextView artist = text(Track.artist(track), 12, 0xFFA3ABC5);
    artist.setMaxLines(1);
    String duration = trackDuration(track);
    artist.setText(
        Track.artist(track).isEmpty() ? track.optString("platform") : Track.artist(track));
    artist.setOnClickListener(v -> openArtist(track));
    labels.addView(artist);
    row.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
    if (!duration.isEmpty()) row.addView(text(duration, 11, MUTED));
    ImageButton more =
        iconButton(
            R.drawable.ic_more,
            tr("Opcje utworu", "Track options"),
            () -> trackOptions(track, group, index, listName));
    more.setContentDescription(tr("Opcje utworu", "Track options"));
    more.setMinimumWidth(0);
    row.addView(more, new LinearLayout.LayoutParams(dp(48), dp(48)));
    labels.setOnClickListener(v -> playSelection(track, group, index, listName));
    thumbnail.setOnClickListener(v -> playSelection(track, group, index, listName));
    row.setOnClickListener(v -> playSelection(track, group, index, listName));
    return row;
  }

  private void trackOptions(JSONObject track, JSONArray group, int index, String name) {
    List<String> labels =
        new ArrayList<>(
            Arrays.asList(
                tr("Odtwórz", "Play"),
                tr("Zagraj jako następny", "Play next"),
                tr("Dodaj na koniec kolejki", "Add to queue"),
                tr("Dodaj do playlisty", "Add to playlist"),
                tr("Otwórz artystę / kanał", "Open artist / channel")));
    boolean suggested = "@recommendations".equals(name);
    if (suggested) labels.add(tr("Usuń z propozycji", "Remove suggestion"));
    else if (!name.isEmpty())
      labels.addAll(
          Arrays.asList(
              tr("Przesuń wyżej", "Move up"),
              tr("Przesuń niżej", "Move down"),
              tr("Usuń z playlisty", "Remove from playlist")));
    new AlertDialog.Builder(this)
        .setTitle(track.optString("title"))
        .setItems(
            labels.toArray(new String[0]),
            (d, i) -> {
              switch (i) {
                case 0:
                  playSelection(track, group, index, name);
                  break;
                case 1:
                  addQueue(track, true);
                  break;
                case 2:
                  addQueue(track, false);
                  break;
                case 3:
                  saveToPlaylist(track);
                  break;
                case 4:
                  openArtist(track);
                  break;
                case 5:
                  if (suggested) {
                    if (PlaybackService.active != null)
                      PlaybackService.active.removeRecommendation(track);
                    renderPage();
                    break;
                  }
                  if (index > 0)
                    mutate(
                        "move",
                        CrowApp.obj("name", name, "from", index, "to", index - 1),
                        this::renderPage);
                  break;
                case 6:
                  if (index < group.length() - 1)
                    mutate(
                        "move",
                        CrowApp.obj("name", name, "from", index, "to", index + 1),
                        this::renderPage);
                  break;
                case 7:
                  mutate("remove", CrowApp.obj("name", name, "index", index), this::renderPage);
              }
            })
        .show();
  }

  private void playSelection(JSONObject track, JSONArray group, int index, String listName) {
    if (listName.isEmpty() || listName.equals("@recommendations"))
      playTracks(new JSONArray().put(track), 0);
    else playTracks(group, index);
  }

  private void playTracks(JSONArray tracks, int index) {
    if (controller == null) {
      toast(tr("Odtwarzacz się łączy", "Player is connecting"));
      return;
    }
    if (tracks.length() == 0) return;
    List<MediaItem> queue = new ArrayList<>();
    for (int i = 0; i < tracks.length(); i++) {
      JSONObject t = tracks.optJSONObject(i);
      if (t != null) queue.add(Track.item(t));
    }
    if (PlaybackService.active != null) PlaybackService.active.startSession();
    controller.setMediaItems(queue, index, 0);
    controller.prepare();
    controller.play();
    updatePlayer();
  }

  /** "Play" on a playlist: its own order, even after an earlier shuffled start. */
  private void playInOrder(JSONArray tracks) {
    if (controller != null) controller.setShuffleModeEnabled(false);
    playTracks(tracks, 0);
  }

  /** Starts a playlist shuffled straight away, from a random track. */
  private void playShuffled(JSONArray tracks) {
    if (controller == null || tracks == null || tracks.length() == 0) {
      playTracks(tracks == null ? new JSONArray() : tracks, 0);
      return;
    }
    controller.setShuffleModeEnabled(true);
    playTracks(tracks, new Random().nextInt(tracks.length()));
    toast(tr("Odtwarzam losowo", "Shuffling"));
  }

  private void addQueue(JSONObject track, boolean next) {
    if (controller == null) return;
    editQueue();
    int position =
        next
            ? Math.min(controller.getMediaItemCount(), controller.getCurrentMediaItemIndex() + 1)
            : controller.getMediaItemCount();
    controller.addMediaItem(position, Track.item(track));
    if (PlaybackService.active != null) PlaybackService.active.removeRecommendation(track);
    toast(tr("Dodano do kolejki", "Added to queue"));
  }

  private void editQueue() {
    if (PlaybackService.active != null) PlaybackService.active.editQueue();
  }

  private void togglePlayback() {
    if (controller == null) return;
    if (playbackRequested()) controller.pause();
    else if (controller.getMediaItemCount() > 0) {
      editQueue();
      if (controller.getPlaybackState() == Player.STATE_ENDED) controller.seekToDefaultPosition();
      controller.prepare();
      controller.play();
    }
  }

  private JSONArray currentContext() {
    JSONArray list = new JSONArray();
    if (controller != null && controller.getCurrentMediaItem() != null)
      list.put(Track.json(controller.getCurrentMediaItem()));
    return list;
  }

  private void renderQueue() {
    titleView.setText(tr("Kolejka", "Queue"));
    if (controller != null && controller.getCurrentMediaItem() != null) {
      sectionAction(
          tr("Teraz odtwarzane", "Now playing"),
          R.drawable.ic_stop,
          tr("Zatrzymaj odtwarzanie", "Stop playback"),
          () -> {
            if (PlaybackService.active != null) PlaybackService.active.stopPlayback();
            else if (controller != null) controller.stop();
          });
      JSONObject current = Track.json(controller.getCurrentMediaItem());
      LinearLayout currentRow = queueTrackRow(current, true);
      currentRow.setOnClickListener(v -> fullPlayer());
      currentRow.setContentDescription(
          tr("Otwórz odtwarzacz: ", "Open player: ") + current.optString("title"));
      ImageButton expand =
          iconButton(R.drawable.ic_queue, tr("Otwórz odtwarzacz", "Open player"), this::fullPlayer);
      currentRow.addView(expand, new LinearLayout.LayoutParams(dp(48), dp(48)));
      content.addView(currentRow);
    }
    int start = controller == null ? 0 : Math.max(0, controller.getCurrentMediaItemIndex() + 1);
    int count = controller == null ? 0 : Math.max(0, controller.getMediaItemCount() - start);
    section(tr("Następne", "Up next") + "  ·  " + count);
    if (count == 0) {
      emptyState(
          tr("Miejsce na kolejny utwór", "Room for your next track"),
          tr(
              "Dodaj muzykę z wyszukiwarki lub playlisty. Pojawi się tutaj.",
              "Add music from search or a playlist. It will appear here."));
      if (!PlaybackService.recommendations.isEmpty()) content.addView(emptyQueueDropZone(start));
    } else {
      LinearLayout list = column();
      content.addView(list);
      dropZone(list, ZONE_QUEUE, start);
      appendQueueRows(list, start, queueOrderKey());
    }
    sectionAction(
        tr("Dla Ciebie", "For you"),
        R.drawable.ic_repeat,
        tr("Odśwież propozycje", "Refresh suggestions"),
        () -> {
          if (PlaybackService.active != null) PlaybackService.active.refreshRecommendations(true);
          toast(tr("Szukam propozycji…", "Looking for suggestions…"));
        });
    content.addView(
        text(
            tr("Zagrają, gdy skończy się Twoja kolejka.", "They play when your queue ends."),
            12,
            MUTED));
    JSONArray suggestions = new JSONArray();
    for (JSONObject t : PlaybackService.recommendations) suggestions.put(t);
    LinearLayout suggestionList = column();
    content.addView(suggestionList);
    dropZone(suggestionList, ZONE_SUGGESTIONS, 0);
    appendSuggestionRows(suggestionList, suggestions);
    suggestionStatus = text(suggestionMessage(), 13, MUTED);
    suggestionStatus.setTag("suggestion-status");
    content.addView(suggestionStatus);
    queueFingerprint = queueKey();
  }

  private void appendQueueRows(LinearLayout list, int start, String snapshot) {
    if (controller == null) return;
    int end = Math.min(controller.getMediaItemCount(), start + 50);
    for (int i = start; i < end; i++) {
      int index = i;
      MediaItem expected = controller.getMediaItemAt(index);
      JSONObject track = Track.json(expected);
      LinearLayout row = queueTrackRow(track, false);
      row.setTag("queue-row");
      ImageView handle = new ImageView(this);
      handle.setImageResource(R.drawable.ic_drag);
      handle.setImageTintList(ColorStateList.valueOf(MUTED));
      handle.setPadding(dp(8), dp(12), dp(4), dp(12));
      handle.setContentDescription(
          tr("Przeciągnij, aby zmienić kolejność: ", "Drag to reorder: ") + track.optString("title"));
      handle.setOnTouchListener(
          (v, event) -> {
            if (event.getActionMasked() != MotionEvent.ACTION_DOWN) return false;
            startDrag(ZONE_QUEUE, index, expected, track, row);
            return true;
          });
      row.addView(handle, new LinearLayout.LayoutParams(dp(36), dp(48)));
      ImageButton more =
          iconButton(
              R.drawable.ic_more, tr("Opcje: ", "Options: ") + track.optString("title"), () -> {});
      more.setOnClickListener(v -> queueOptions(more, index, expected, snapshot));
      row.addView(more, new LinearLayout.LayoutParams(dp(48), dp(48)));
      row.setOnClickListener(v -> queueAction(index, expected, snapshot, 0));
      // Hold a row (or touch its handle) to drag it to a new place in the queue.
      row.setOnLongClickListener(
          v -> {
            startDrag(ZONE_QUEUE, index, expected, track, row);
            return true;
          });
      list.addView(row);
    }
    if (end < controller.getMediaItemCount()) {
      Button more = button(tr("Pokaż kolejne utwory", "Show more tracks"), () -> {});
      more.setOnClickListener(
          v -> {
            if (!snapshot.equals(queueOrderKey())) {
              renderPage();
              return;
            }
            list.removeView(more);
            appendQueueRows(list, end, snapshot);
          });
      list.addView(more);
    }
  }

  private void startDrag(int source, int index, MediaItem item, JSONObject track, View row) {
    if (controller == null || dragFrom >= 0) return;
    dragSource = source;
    dragFrom = index;
    dragItem = item;
    dragTrack = track;
    draggedRow = row;
    row.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS);
    boolean started =
        row.startDragAndDrop(
            android.content.ClipData.newPlainText("track", track.optString("title")),
            new View.DragShadowBuilder(row),
            null,
            0);
    if (started) row.setAlpha(0.35f);
    else clearDrag();
  }

  private void clearDrag() {
    if (draggedRow != null) draggedRow.setAlpha(1f);
    dragSource = -1;
    dragFrom = -1;
    dragItem = null;
    dragTrack = null;
    draggedRow = null;
  }

  /**
   * A list that accepts drops anywhere inside it (gaps and edges included). The drop
   * position is worked out from the pointer, so rows need no listeners of their own.
   */
  private void dropZone(LinearLayout zone, int kind, int start) {
    zone.setOnDragListener(
        (v, event) -> {
          switch (event.getAction()) {
            case DragEvent.ACTION_DRAG_STARTED:
              // Suggestions may move into the queue; queued tracks stay in the queue.
              return dragFrom >= 0 && (kind == ZONE_QUEUE || dragSource == ZONE_SUGGESTIONS);
            case DragEvent.ACTION_DRAG_ENTERED:
            case DragEvent.ACTION_DRAG_LOCATION:
              showDropSlot(zone, dropSlot(zone, event.getY()));
              scrollDuringDrag(zone, event.getY());
              return true;
            case DragEvent.ACTION_DRAG_EXITED:
              showDropSlot(zone, -1);
              return true;
            case DragEvent.ACTION_DROP:
              int slot = dropSlot(zone, event.getY());
              showDropSlot(zone, -1);
              finishDrag(kind, start, slot);
              return true;
            case DragEvent.ACTION_DRAG_ENDED:
              showDropSlot(zone, -1);
              if (dragFrom >= 0)
                handler.post(
                    () -> {
                      if (dragFrom < 0) return;
                      clearDrag();
                      refreshAfterQueueEdit(); // apply refreshes held back while dragging
                    });
              return true;
            default:
              return false;
          }
        });
  }

  private static boolean draggableRow(View child) {
    return "queue-row".equals(child.getTag()) || "suggestion-row".equals(child.getTag());
  }

  /** Insertion position among the rows of a zone: 0 before the first row, n after the last. */
  private int dropSlot(LinearLayout zone, float y) {
    int slot = 0;
    for (int i = 0; i < zone.getChildCount(); i++) {
      View child = zone.getChildAt(i);
      if (!draggableRow(child)) continue;
      if (y < child.getTop() + child.getHeight() / 2f) return slot;
      slot++;
    }
    return slot;
  }

  private void showDropSlot(LinearLayout zone, int slot) {
    List<View> rows = new ArrayList<>();
    for (int i = 0; i < zone.getChildCount(); i++)
      if (draggableRow(zone.getChildAt(i))) rows.add(zone.getChildAt(i));
    for (View row : rows) row.setForeground(null);
    zone.setForeground(null);
    if (slot < 0) return;
    if (rows.isEmpty()) zone.setForeground(dropLine(false));
    else if (slot < rows.size()) rows.get(slot).setForeground(dropLine(false));
    else rows.get(rows.size() - 1).setForeground(dropLine(true));
  }

  private void finishDrag(int kind, int start, int slot) {
    if (controller == null || dragFrom < 0 || dragTrack == null) return;
    int first = controller.getCurrentMediaItemIndex() + 1;
    int count = controller.getMediaItemCount();
    if (kind == ZONE_QUEUE) {
      int insert = Math.max(first, Math.min(start + slot, count));
      if (dragSource == ZONE_QUEUE) {
        int from = queueIndexOf(dragItem, dragFrom);
        if (from < first) {
          toast(
              tr(
                  "Kolejka się zmieniła. Przeciągnij utwór ponownie.",
                  "Queue changed. Drag the track again."));
          return;
        }
        int to = insert > from ? insert - 1 : insert; // index once taken out of the list
        to = Math.max(first, Math.min(to, count - 1));
        if (to == from) return;
        editQueue();
        controller.moveMediaItem(from, to);
      } else {
        editQueue();
        controller.addMediaItem(insert, Track.item(dragTrack));
        if (PlaybackService.active != null) PlaybackService.active.removeRecommendation(dragTrack);
        toast(tr("Dodano do kolejki", "Added to queue"));
      }
    } else if (dragSource == ZONE_SUGGESTIONS && PlaybackService.active != null) {
      String url = dragTrack.optString("url");
      int from = -1;
      List<JSONObject> list = PlaybackService.recommendations;
      for (int i = 0; i < list.size(); i++)
        if (url.equals(list.get(i).optString("url"))) {
          from = i;
          break;
        }
      if (from < 0) return;
      int to = slot > from ? slot - 1 : slot;
      if (to == from) return;
      PlaybackService.active.moveRecommendation(url, to);
    }
  }

  /** Where a dragged queue entry is now, checked by identity rather than by position alone. */
  private int queueIndexOf(MediaItem item, int hint) {
    if (controller == null || item == null) return -1;
    int count = controller.getMediaItemCount();
    if (hint >= 0 && hint < count && item.equals(controller.getMediaItemAt(hint))) return hint;
    for (int i = 0; i < count; i++) if (item.equals(controller.getMediaItemAt(i))) return i;
    return -1;
  }

  /** Suggestion rows with a drag handle: reorder them, or drag one up into the queue. */
  private void appendSuggestionRows(LinearLayout zone, JSONArray suggestions) {
    for (int i = 0; i < suggestions.length(); i++) {
      JSONObject track = suggestions.optJSONObject(i);
      if (track == null) continue;
      int index = i;
      LinearLayout row = (LinearLayout) trackRow(track, suggestions, i, "@recommendations");
      row.setTag("suggestion-row");
      ImageView handle = new ImageView(this);
      handle.setImageResource(R.drawable.ic_drag);
      handle.setImageTintList(ColorStateList.valueOf(MUTED));
      handle.setPadding(dp(8), dp(12), dp(4), dp(12));
      handle.setContentDescription(
          tr("Przeciągnij propozycję: ", "Drag suggestion: ") + track.optString("title"));
      handle.setOnTouchListener(
          (v, event) -> {
            if (event.getActionMasked() != MotionEvent.ACTION_DOWN) return false;
            startDrag(ZONE_SUGGESTIONS, index, null, track, row);
            return true;
          });
      row.addView(handle, row.getChildCount() - 1, new LinearLayout.LayoutParams(dp(36), dp(48)));
      row.setOnLongClickListener(
          v -> {
            startDrag(ZONE_SUGGESTIONS, index, null, track, row);
            return true;
          });
      zone.addView(row);
    }
  }

  /** An empty queue still accepts suggestions dragged into it. */
  private LinearLayout emptyQueueDropZone(int start) {
    LinearLayout zone = column();
    zone.setMinimumHeight(dp(52));
    zone.setGravity(Gravity.CENTER_VERTICAL);
    GradientDrawable dashed = new GradientDrawable();
    dashed.setCornerRadius(dp(12));
    dashed.setStroke(dp(1), blend(MUTED, 0xFF10131F, 0.4f), dp(6), dp(4));
    zone.setBackground(dashed);
    zone.setPadding(dp(14), dp(10), dp(14), dp(10));
    zone.addView(
        text(
            tr(
                "Przeciągnij tu propozycję, aby dodać ją do kolejki.",
                "Drag a suggestion here to add it to the queue."),
            12,
            MUTED));
    dropZone(zone, ZONE_QUEUE, start);
    return zone;
  }

  /** A short accent line where the dragged track will land. */
  private Drawable dropLine(boolean below) {
    android.graphics.drawable.LayerDrawable line =
        new android.graphics.drawable.LayerDrawable(
            new Drawable[] {new android.graphics.drawable.ColorDrawable(accent)});
    line.setLayerHeight(0, dp(3));
    line.setLayerGravity(
        0, (below ? Gravity.BOTTOM : Gravity.TOP) | Gravity.FILL_HORIZONTAL);
    return line;
  }

  /** Scrolls the surrounding page while a track is dragged near its top or bottom edge. */
  private void scrollDuringDrag(View row, float y) {
    View parent = row;
    while (parent != null && !(parent instanceof ScrollView))
      parent = parent.getParent() instanceof View ? (View) parent.getParent() : null;
    if (parent == null) return;
    int[] rowAt = new int[2], scrollAt = new int[2];
    row.getLocationOnScreen(rowAt);
    parent.getLocationOnScreen(scrollAt);
    float position = rowAt[1] + y - scrollAt[1];
    int edge = dp(96);
    if (position < edge) ((ScrollView) parent).smoothScrollBy(0, -dp(28));
    else if (position > parent.getHeight() - edge) ((ScrollView) parent).smoothScrollBy(0, dp(28));
  }

  /** Redraws the queue where it is shown, keeping the scroll position. */
  private void refreshAfterQueueEdit() {
    if (playerQueue != null && playerDialog != null && playerDialog.isShowing())
      renderPlayerQueue();
    if (tab != 3 || !playlist.isEmpty() || artistTrack != null) return;
    int scroll = pageScroll.getScrollY();
    renderPage();
    content.animate().cancel();
    content.setAlpha(1f);
    content.setTranslationY(0f);
    pageScroll.post(() -> pageScroll.scrollTo(0, scroll));
  }

  private LinearLayout musicRow(boolean highlighted) {
    LinearLayout row = row();
    row.setPadding(dp(8), dp(9), 0, dp(9));
    row.setMinimumHeight(dp(68));
    row.setBackground(ripple(highlighted ? blend(accent, SURFACE, 0.12f) : Color.TRANSPARENT, 12));
    row.setLayoutParams(new LinearLayout.LayoutParams(-1, -2));
    return row;
  }

  private LinearLayout queueTrackRow(JSONObject track, boolean highlighted) {
    LinearLayout row = musicRow(highlighted);
    ImageView cover = art(track.optString("thumbnail_url"), false);
    row.addView(cover, new LinearLayout.LayoutParams(dp(46), dp(46)));
    LinearLayout labels = column();
    labels.setPadding(dp(12), 0, dp(8), 0);
    TextView title =
        text(
            track.optString("title", tr("Utwór", "Track")), 14, highlighted ? accent : Color.WHITE);
    title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    title.setMaxLines(2);
    labels.addView(title);
    String artist = Track.artist(track);
    TextView subtitle = text(artist.isEmpty() ? track.optString("platform") : artist, 12, MUTED);
    subtitle.setMaxLines(1);
    labels.addView(subtitle);
    row.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
    String duration = trackDuration(track);
    if (!duration.isEmpty()) {
      TextView length = text(duration, 11, MUTED);
      length.setMaxLines(1);
      row.addView(length);
    }
    return row;
  }

  private String trackDuration(JSONObject track) {
    double duration = track.optDouble("duration");
    return duration > 0 ? clock((long) (duration * 1000)) : "";
  }

  private void sectionAction(String label, int icon, String actionLabel, Runnable action) {
    LinearLayout header = row();
    TextView title = text(label, 17, Color.WHITE);
    title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
    header.addView(
        iconButton(icon, actionLabel, action), new LinearLayout.LayoutParams(dp(48), dp(48)));
    header.setPadding(0, dp(8), 0, 0);
    content.addView(header);
  }

  private void queueOptions(View anchor, int index, MediaItem expected, String snapshot) {
    PopupMenu popup = new PopupMenu(this, anchor);
    String[] actions = {
      tr("Odtwórz teraz", "Play now"),
      tr("Odtwórz jako następny", "Play next"),
      tr("Przesuń wyżej", "Move up"),
      tr("Przesuń niżej", "Move down"),
      tr("Usuń z kolejki", "Remove from queue")
    };
    for (int i = 0; i < actions.length; i++) popup.getMenu().add(0, i, i, actions[i]);
    if (controller != null) {
      popup.getMenu().findItem(1).setEnabled(index > controller.getCurrentMediaItemIndex() + 1);
      popup.getMenu().findItem(2).setEnabled(index > controller.getCurrentMediaItemIndex() + 1);
      popup.getMenu().findItem(3).setEnabled(index < controller.getMediaItemCount() - 1);
    }
    popup.setOnMenuItemClickListener(
        item -> {
          queueAction(index, expected, snapshot, item.getItemId());
          return true;
        });
    popup.show();
  }

  private void queueAction(int index, MediaItem expected, String snapshot, int action) {
    // A menu may stay open while playback advances or the queue changes.
    if (controller == null
        || !snapshot.equals(queueOrderKey())
        || index <= controller.getCurrentMediaItemIndex()
        || index >= controller.getMediaItemCount()
        || !expected.equals(controller.getMediaItemAt(index))) {
      toast(
          tr(
              "Kolejka się zmieniła. Wybierz utwór ponownie.",
              "Queue changed. Select the track again."));
      return;
    }
    int first = controller.getCurrentMediaItemIndex() + 1;
    editQueue();
    switch (action) {
      case 0:
        controller.seekTo(index, 0);
        controller.prepare();
        controller.play();
        break;
      case 1:
        if (index > first) controller.moveMediaItem(index, first);
        break;
      case 2:
        if (index > first) controller.moveMediaItem(index, index - 1);
        break;
      case 3:
        if (index + 1 < controller.getMediaItemCount()) controller.moveMediaItem(index, index + 1);
        break;
      case 4:
        controller.removeMediaItem(index);
        break;
      default:
        return;
    }
    // Keep the scroll position when editing the queue, without flashing the whole page.
    int scroll = pageScroll.getScrollY();
    renderPage();
    content.animate().cancel();
    content.setAlpha(1f);
    content.setTranslationY(0f);
    pageScroll.post(() -> pageScroll.scrollTo(0, scroll));
  }

  /** The queue alone (order and current track), for validating menu actions and drags. */
  private String queueOrderKey() {
    if (controller == null) return "";
    StringBuilder key = new StringBuilder().append(controller.getCurrentMediaItemIndex());
    for (int i = 0; i < controller.getMediaItemCount(); i++)
      key.append("|").append(controller.getMediaItemAt(i).mediaId);
    return key.toString();
  }

  private String queueKey() {
    if (controller == null) return "";
    StringBuilder key = new StringBuilder().append(controller.getCurrentMediaItemIndex());
    for (int i = 0; i < controller.getMediaItemCount(); i++)
      key.append("|")
          .append(controller.getMediaItemAt(i).mediaId.length())
          .append(":")
          .append(controller.getMediaItemAt(i).mediaId);
    for (JSONObject t : PlaybackService.recommendations) key.append(t.optString("url"));
    return key.toString();
  }

  private void renderSettings() {
    titleView.setText(tr("Ustaw po swojemu.", "Make it yours."));
    section(tr("Wygląd i język", "Appearance and language"));
    content.addView(
        button(
            tr("Język: Polski", "Language: English"),
            () ->
                new AlertDialog.Builder(this)
                    .setItems(
                        new String[] {"Polski", "English"},
                        (d, i) ->
                            mutate(
                                "settings",
                                CrowApp.obj("LANGUAGE", i == 0 ? "pl" : "en"),
                                () -> {
                                  buildShell();
                                  renderPage();
                                }))
                    .show()));
    content.addView(
        button(
            tr("Kolor akcentu", "Accent colour"),
            () ->
                new AlertDialog.Builder(this)
                    .setItems(
                        new String[] {
                          "Deep Purple", "Midnight Blue", "Forest Green", "Crimson Red"
                        },
                        (d, i) ->
                            mutate(
                                "settings",
                                CrowApp.obj(
                                    "ACCENT_COLOR",
                                    new String[] {"#9672FF", "#3B82F6", "#10B981", "#EF4444"}[i]),
                                () -> {
                                  buildShell();
                                  renderPage();
                                }))
                    .show()));
    section(tr("Odtwarzanie i dźwięk", "Playback and sound"));
    settingSwitch(tr("Przygotuj następny utwór", "Prepare next track"), "PREFETCH_ENABLED", true);
    settingSwitch("Crossfade", "CROSSFADE_ENABLED", false);
    slider(tr("Crossfade (sekundy)", "Crossfade (seconds)"), "CROSSFADE_DURATION", 1, 15, 5);
    slider(tr("Basy (dB)", "Bass (dB)"), "BASS_GAIN", -15, 15, 0);
    slider(tr("Tony wysokie (dB)", "Treble (dB)"), "TREBLE_GAIN", -15, 15, 0);
    content.addView(
        text(
            tr(
                "Korektor korzysta z efektów dźwiękowych telefonu. Crossfade wymaga przygotowanego"
                    + " następnego utworu.",
                "Equalizer uses the phone's audio effects. Crossfade requires the next track to be"
                    + " prepared."),
            12,
            0xFFA3ABC5));
    section("Google Drive");
    android.content.SharedPreferences prefs = getSharedPreferences("drive", MODE_PRIVATE);
    String email = prefs.getString("email", "");
    content.addView(
        text(
            email.isEmpty()
                ? tr("Wspólna kopia z wersją PC", "Shared backup with the PC app")
                : email,
            14,
            0xFFA3ABC5));
    content.addView(
        button(
            tr("Zaloguj / Przywróć kopię…", "Sign in / Restore backup…"),
            () -> authorizeDrive("list")));
    content.addView(
        button(tr("Zapisz kopię teraz", "Back up now"), () -> authorizeDrive("upload")));
    Switch automatic = new Switch(this);
    automatic.setText(tr("Automatyczna kopia po zmianach", "Automatic backup after changes"));
    automatic.setChecked(prefs.getBoolean("auto", false));
    automatic.setTextColor(Color.WHITE);
    automatic.setOnCheckedChangeListener(
        (b, value) -> {
          prefs.edit().putBoolean("auto", value).apply();
          if (value) authorizeDrive("connect");
        });
    styleSwitch(automatic);
    content.addView(automatic);
    Switch history = new Switch(this);
    history.setText(tr("Dołącz historię słuchania", "Include listening history"));
    history.setTextColor(Color.WHITE);
    history.setChecked(prefs.getBoolean("history", false));
    history.setOnCheckedChangeListener(
        (b, value) -> prefs.edit().putBoolean("history", value).apply());
    styleSwitch(history);
    content.addView(history);
    if (!email.isEmpty())
      content.addView(
          button(
              tr("Odłącz Google", "Disconnect Google"),
              () -> DriveSync.disconnect(this, this::renderPage, this::showError)));
    content.addView(text(DriveSync.status, 12, 0xFFA3ABC5));
    section(tr("Kopia w pliku", "Backup file"));
    content.addView(
        button(
            tr("Eksportuj kopię JSON", "Export JSON backup"),
            () -> {
              Intent intent =
                  new Intent(Intent.ACTION_CREATE_DOCUMENT)
                      .setType("application/json")
                      .addCategory(Intent.CATEGORY_OPENABLE)
                      .putExtra(Intent.EXTRA_TITLE, DriveClient.NAME);
              startActivityForResult(intent, 31);
            }));
    content.addView(
        button(tr("Przywróć z pliku JSON…", "Restore JSON file…"), () -> openDocument("*/*", 30)));
    content.addView(
        text(
            tr(
                "Przywrócenie łączy playlisty i zachowuje kopię awaryjną. Dźwięk i dane logowania"
                    + " nie są częścią kopii.",
                "Restore merges playlists and keeps a recovery copy. Audio and sign-in data are not"
                    + " backed up."),
            12,
            0xFFA3ABC5));
    content.addView(
        button(
            tr("Licencje i informacje", "Licenses and information"),
            () ->
                new AlertDialog.Builder(this)
                    .setTitle("Music Crow 0.5.0-dev")
                    .setMessage(
                        "Music Crow: MIT\n"
                            + "AndroidX Media3: Apache-2.0\n"
                            + "Chaquopy: MIT\n"
                            + "Python: PSF\n"
                            + "yt-dlp: Unlicense\n"
                            + "Glide: BSD / Apache-2.0\n"
                            + "Google Play services: Google SDK terms\n\n"
                            + "https://github.com/Miniu123/Music_Crow")
                    .setNeutralButton(
                        tr("Czytaj licencje", "Read licenses"), (dialog, which) -> showLicenses())
                    .setPositiveButton("OK", null)
                    .show()));
  }

  private void showLicenses() {
    runTask(
        () -> getAssets().list("licenses"),
        files -> {
          if (files == null) return;
          Arrays.sort(files);
          new AlertDialog.Builder(this)
              .setTitle(tr("Licencje", "Licenses"))
              .setItems(
                  files,
                  (dialog, index) -> {
                    runTask(
                        () -> {
                          try (InputStream input = getAssets().open("licenses/" + files[index])) {
                            return new String(
                                DriveClient.readLimited(input, 1024 * 1024),
                                StandardCharsets.UTF_8);
                          }
                        },
                        body -> {
                          ScrollView scroll = new ScrollView(this);
                          TextView document = text(body, 12, Color.WHITE);
                          document.setTextIsSelectable(true);
                          document.setPadding(dp(16), dp(16), dp(16), dp(16));
                          scroll.addView(document);
                          new AlertDialog.Builder(this)
                              .setTitle(files[index])
                              .setView(scroll)
                              .setPositiveButton("OK", null)
                              .show();
                        },
                        this::showError);
                  })
              .show();
        },
        this::showError);
  }

  private void settingSwitch(String label, String key, boolean fallback) {
    Switch toggle = new Switch(this);
    toggle.setText(label);
    toggle.setTextColor(Color.WHITE);
    toggle.setChecked(app.settings().optBoolean(key, fallback));
    toggle.setOnCheckedChangeListener(
        (button, value) -> mutate("settings", CrowApp.obj(key, value), () -> {}));
    styleSwitch(toggle);
    content.addView(toggle);
  }

  private void slider(String label, String key, int min, int max, int fallback) {
    int current = app.settings().optInt(key, fallback);
    TextView caption = text(label + ": " + current, 14, 0xFFA3ABC5);
    content.addView(caption);
    SeekBar slider = new SeekBar(this);
    tintSeek(slider);
    slider.setContentDescription(label);
    slider.setMax(max - min);
    slider.setProgress(current - min);
    slider.setOnSeekBarChangeListener(
        new SeekBar.OnSeekBarChangeListener() {
          public void onStartTrackingTouch(SeekBar b) {}

          public void onProgressChanged(SeekBar b, int p, boolean user) {
            caption.setText(label + ": " + (p + min));
          }

          public void onStopTrackingTouch(SeekBar b) {
            mutate("settings", CrowApp.obj(key, b.getProgress() + min), () -> {});
          }
        });
    content.addView(slider);
  }

  private void authorizeDrive(String action) {
    if (authorizationBusy) return;
    authorizationBusy = true;
    driveOperation = action;
    DriveSync.authorize(
        this,
        drive -> {
          authorizationBusy = false;
          driveAuthorized(drive);
        },
        message -> {
          authorizationBusy = false;
          showError(message);
        });
  }

  private void driveAuthorized(DriveClient drive) {
    String operation = driveOperation;
    if (operation.equals("connect")) {
      toast(
          tr(
              "Połączono. Najpierw przywróć istniejącą kopię z PC.",
              "Connected. Restore the existing PC backup first."));
      renderPage();
      return;
    }
    if (operation.equals("upload")) {
      if (!DriveSync.uploading.compareAndSet(false, true)) {
        toast(tr("Kopia już trwa", "Backup is already running"));
        return;
      }
      runTask(
          () -> {
            try {
              drive.upload(
                  app.call(
                          "backup",
                          CrowApp.obj(
                              "history",
                              getSharedPreferences("drive", MODE_PRIVATE)
                                  .getBoolean("history", false)))
                      .getBytes(StandardCharsets.UTF_8));
              return true;
            } finally {
              DriveSync.uploading.set(false);
            }
          },
          ok -> {
            DriveSync.status = tr("Kopia zapisana", "Backup saved");
            toast(DriveSync.status);
            renderPage();
          },
          this::showError);
      return;
    }
    toast(tr("Pobieranie listy kopii…", "Loading backups…"));
    runTask(
        drive::list,
        files -> {
          if (files.isEmpty()) {
            showError(
                tr(
                    "Brak kopii. Zapisz ją na PC na tym samym koncie Google.",
                    "No backup. Create one on PC with the same Google account."));
            return;
          }
          String[] labels = new String[files.size()];
          for (int i = 0; i < labels.length; i++)
            labels[i] =
                files.get(i).optString("name") + "\n" + files.get(i).optString("modifiedTime");
          new AlertDialog.Builder(this)
              .setTitle(tr("Wybierz kopię", "Choose backup"))
              .setItems(
                  labels,
                  (dialog, index) -> {
                    JSONObject file = files.get(index);
                    runTask(
                        () -> drive.download(file),
                        raw -> previewRestore(raw, drive, file),
                        this::showError);
                  })
              .show();
        },
        this::showError);
  }

  private void previewRestore(byte[] raw, DriveClient drive, JSONObject file) {
    runTask(
        () -> {
          JSONObject snapshot = new JSONObject(new String(raw, StandardCharsets.UTF_8));
          JSONObject counts =
              new JSONObject(app.call("preview", CrowApp.obj("snapshot", snapshot)));
          validateCovers(snapshot);
          return new JSONObject[] {snapshot, counts};
        },
        data -> {
          String message =
              data[1].optInt("playlists")
                  + tr(" playlist, ", " playlists, ")
                  + data[1].optInt("tracks")
                  + tr(
                      " utworów.\nUstawienia zostaną przywrócone; obecne playlisty zachowane.",
                      " tracks.\nSettings will be restored; existing playlists will be kept.");
          confirm(
              tr("Przywrócić kopię?", "Restore backup?"),
              message,
              () ->
                  runTask(
                      () -> {
                        app.call("restore", CrowApp.obj("snapshot", data[0]));
                        if (drive != null) drive.acknowledge(file, raw);
                        return true;
                      },
                      ok -> {
                        buildShell();
                        renderPage();
                        toast(tr("Kopia przywrócona", "Backup restored"));
                      },
                      this::showError));
        },
        this::showError);
  }

  private void validateCovers(JSONObject snapshot) throws Exception {
    JSONObject lists = snapshot.getJSONObject("playlists");
    Iterator<String> keys = lists.keys();
    while (keys.hasNext()) {
      String cover = lists.getJSONObject(keys.next()).optString("cover");
      if (!cover.isEmpty()) {
        byte[] bytes = android.util.Base64.decode(cover, android.util.Base64.DEFAULT);
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
        if (options.outWidth <= 0
            || options.outHeight <= 0
            || options.outWidth > 20000
            || options.outHeight > 20000)
          throw new IOException("Nieprawidłowa okładka / Invalid cover");
      }
    }
  }

  private void openAudio() {
    Intent intent =
        new Intent(Intent.ACTION_OPEN_DOCUMENT)
            .setType("audio/*")
            .addCategory(Intent.CATEGORY_OPENABLE)
            .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
    intent.addFlags(
        Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
    startActivityForResult(intent, 1);
  }

  private void openDocument(String type, int request) {
    startActivityForResult(
        new Intent(Intent.ACTION_OPEN_DOCUMENT).setType(type).addCategory(Intent.CATEGORY_OPENABLE),
        request);
  }

  @Override
  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (request == DriveSync.REQUEST) {
      authorizationBusy = false;
      if (result == RESULT_OK && data != null)
        DriveSync.result(this, data, this::driveAuthorized, this::showError);
      else toast(tr("Logowanie anulowane", "Sign-in cancelled"));
      return;
    }
    if (result != RESULT_OK || data == null) return;
    if (request == 1) {
      List<Uri> uris = new ArrayList<>();
      if (data.getClipData() != null)
        for (int i = 0; i < data.getClipData().getItemCount(); i++)
          uris.add(data.getClipData().getItemAt(i).getUri());
      else if (data.getData() != null) uris.add(data.getData());
      String destination = pendingPlaylist;
      runTask(
          () -> {
            JSONArray tracks = new JSONArray();
            for (Uri uri : uris) {
              getContentResolver()
                  .takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
              String title = "Utwór";
              try (Cursor cursor =
                  getContentResolver()
                      .query(uri, new String[] {OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                if (cursor != null && cursor.moveToFirst() && !cursor.isNull(0))
                  title = cursor.getString(0);
              }
              tracks.put(CrowApp.obj("title", title, "url", uri.toString(), "platform", "Local"));
            }
            return app.call("add", CrowApp.obj("name", destination, "tracks", tracks));
          },
          ok -> {
            playlist = destination;
            renderPage();
          },
          this::showError);
      return;
    }
    Uri uri = data.getData();
    if (uri == null) return;
    if (request == 30)
      runTask(
          () -> {
            try (InputStream input = getContentResolver().openInputStream(uri)) {
              return DriveClient.readLimited(input, DriveClient.MAX);
            }
          },
          raw -> previewRestore(raw, null, null),
          this::showError);
    if (request == 31)
      runTask(
          () -> {
            byte[] raw =
                app.call(
                        "backup",
                        CrowApp.obj(
                            "history",
                            getSharedPreferences("drive", MODE_PRIVATE)
                                .getBoolean("history", false)))
                    .getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
              if (out == null) throw new IOException("Cannot create backup");
              out.write(raw);
            }
            return true;
          },
          ok -> toast(tr("Kopia zapisana", "Backup saved")),
          this::showError);
    if (request == 32) {
      String destination = pendingPlaylist;
      runTask(
          () -> {
            byte[] bytes;
            try (InputStream input = getContentResolver().openInputStream(uri)) {
              bytes = DriveClient.readLimited(input, 5 * 1024 * 1024);
            }
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
            if (options.outWidth <= 0 || options.outHeight <= 0)
              throw new IOException("Invalid image");
            options.inSampleSize =
                Math.max(1, Math.max(options.outWidth, options.outHeight) / 1024);
            options.inJustDecodeBounds = false;
            Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
            if (bitmap == null) throw new IOException("Invalid image");
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, output);
            bitmap.recycle();
            String cover =
                android.util.Base64.encodeToString(
                    output.toByteArray(), android.util.Base64.NO_WRAP);
            return app.call("cover", CrowApp.obj("name", destination, "cover", cover));
          },
          ok -> renderPage(),
          this::showError);
    }
  }

  private String artKey = "";

  private void updatePlayer() {
    if (controller == null || nowTitle == null) return;
    MediaItem item = controller.getCurrentMediaItem();
    JSONObject track = Track.json(item);
    nowTitle.setText(
        item == null ? tr("Wybierz utwór", "Choose a track") : track.optString("title"));
    nowArtist.setText(
        item == null ? tr("Muzyka czeka na Ciebie", "Your music is waiting") : Track.artist(track));
    String image = track.optString("thumbnail_url");
    if (!image.equals(artKey)) {
      artKey = image;
      Glide.with(this)
          .load(image)
          .placeholder(R.drawable.music_crow)
          .transition(DrawableTransitionOptions.withCrossFade(motionEnabled() ? 260 : 0))
          .into(nowArt);
    } else if (item == null) nowArt.setImageResource(R.drawable.music_crow);
    play.setImageResource(playbackRequested() ? R.drawable.ic_pause : R.drawable.ic_play);
    play.setContentDescription(
        playbackRequested() ? tr("Wstrzymaj", "Pause") : tr("Odtwórz", "Play"));
    play.setEnabled(item != null);
    long duration = Math.max(0, controller.getDuration()),
        position = Math.max(0, controller.getCurrentPosition());
    seek.setEnabled(duration > 0 && controller.isCurrentMediaItemSeekable());
    if (!dragging)
      seek.setProgress(duration > 0 ? (int) (position * 1000 / duration) : 0, motionEnabled());
    time.setText(
        clock(position)
            + " / "
            + clock(duration)
            + (controller.getPlaybackState() == Player.STATE_BUFFERING
                ? tr("  •  Wczytywanie…", "  •  Loading…")
                : ""));
    updateExpandedPlayer(track, duration, position);
    if (suggestionStatus != null) suggestionStatus.setText(suggestionMessage());
    if (!PlaybackService.playbackError.isEmpty()) {
      String error = PlaybackService.playbackError;
      PlaybackService.playbackError = "";
      showError(error);
    }
    // Home suggestions refresh only while empty or after "Discover", never on every batch.
    if (tab == 0
        && playlist.isEmpty()
        && artistTrack == null
        && homeSuggestions != null
        && (homeSuggestionsEmpty || (homeRefreshRequested && !PlaybackService.recommendationLoading))
        && !recommendationKey().equals(homeFingerprint)) {
      homeRefreshRequested = false;
      loadHomeSuggestions();
    }
    if (tab == 3
        && playlist.isEmpty()
        && artistTrack == null
        && dragFrom < 0 // never rebuild the rows under a finger mid-drag
        && !queueKey().equals(queueFingerprint)) renderPage();
  }

  private boolean playbackRequested() {
    return controller != null
        && controller.getPlayWhenReady()
        && controller.getPlaybackState() != Player.STATE_IDLE
        && controller.getPlaybackState() != Player.STATE_ENDED;
  }

  private String suggestionMessage() {
    if (PlaybackService.recommendations.isEmpty()) {
      if (PlaybackService.recommendationLoading)
        return tr("Szukam propozycji…", "Finding suggestions…");
      if (PlaybackService.recommendationFailed)
        return tr(
            "Nie udało się pobrać propozycji. Sprawdź połączenie i odśwież.",
            "Couldn't load suggestions. Check your connection and refresh.");
      if (controller != null && controller.getCurrentMediaItem() != null)
        return tr(
            "Brak nowych propozycji dla tego utworu. Spróbuj odświeżyć.",
            "No new suggestions for this track. Try refreshing.");
      return tr(
          "Wybierz utwór lub zapisz playlistę, aby zobaczyć propozycje.",
          "Choose a track or save a playlist to see suggestions.");
    }
    boolean fromSuggestions =
        controller != null
            && !controller.hasNextMediaItem()
            && controller.getRepeatMode() == Player.REPEAT_MODE_OFF;
    if (fromSuggestions) {
      switch (PlaybackService.preparation) {
        case "loading":
          return tr("Przygotowuję pierwszą propozycję…", "Preparing the first suggestion…");
        case "ready":
          return tr("Pierwsza propozycja gotowa do odtwarzania", "First suggestion ready to play");
        case "stream":
          return tr(
              "Propozycja zostanie wczytana przy odtwarzaniu", "Suggestion will load when played");
      }
    }
    return PlaybackService.recommendationLoading
        ? tr("Szukam kolejnych propozycji…", "Finding more suggestions…")
        : "";
  }

  private void fullPlayer() {
    if (controller == null || controller.getCurrentMediaItem() == null) return;
    if (playerDialog != null && playerDialog.isShowing()) return;
    playerDialog = new Dialog(this, android.R.style.Theme_Material_NoActionBar);
    playerDialog
        .getWindow()
        .setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(0xFF10131F));
    playerDialog.getWindow().setStatusBarColor(0xFF10131F);
    playerDialog.getWindow().setNavigationBarColor(0xFF10131F);
    if (motionEnabled()) playerDialog.getWindow().setWindowAnimations(R.style.PlayerMotion);
    LinearLayout box = column();
    box.setPadding(dp(24), dp(20), dp(24), dp(24));
    LinearLayout header = row();
    header.addView(
        iconButton(
            R.drawable.ic_down,
            tr("Zamknij odtwarzacz", "Close player"),
            () -> playerDialog.dismiss()),
        new LinearLayout.LayoutParams(dp(48), dp(48)));
    TextView caption = text(tr("TERAZ ODTWARZANE", "NOW PLAYING"), 11, MUTED);
    caption.setLetterSpacing(0.12f);
    caption.setGravity(Gravity.CENTER);
    header.addView(caption, new LinearLayout.LayoutParams(0, -2, 1));
    header.addView(
        iconButton(R.drawable.ic_more, tr("Opcje utworu", "Track options"), () -> {}),
        new LinearLayout.LayoutParams(dp(48), dp(48)));
    View options = header.getChildAt(header.getChildCount() - 1);
    options.setOnClickListener(v -> playerOptions(v));
    box.addView(header);
    expandedArt = art("", false);
    int size =
        Math.min(
            360,
            (int)
                    (getResources().getDisplayMetrics().widthPixels
                        / getResources().getDisplayMetrics().density)
                - 64);
    LinearLayout.LayoutParams artParams = new LinearLayout.LayoutParams(dp(size), dp(size));
    artParams.gravity = Gravity.CENTER_HORIZONTAL;
    artParams.setMargins(0, dp(24), 0, dp(24));
    box.addView(expandedArt, artParams);
    expandedTitle = text("", 24, Color.WHITE);
    expandedTitle.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    expandedTitle.setMaxLines(3);
    expandedArtist = text("", 16, MUTED);
    expandedArtist.setMaxLines(2);
    LinearLayout titleRow = row();
    LinearLayout names = column();
    names.addView(expandedTitle);
    names.addView(expandedArtist);
    titleRow.addView(names, new LinearLayout.LayoutParams(0, -2, 1));
    ImageButton addToPlaylist =
        iconButton(
            R.drawable.ic_playlist_add,
            tr("Dodaj do playlisty", "Add to playlist"),
            () -> {
              if (controller != null && controller.getCurrentMediaItem() != null)
                saveToPlaylist(Track.json(controller.getCurrentMediaItem()));
            });
    GradientDrawable ring = new GradientDrawable();
    ring.setShape(GradientDrawable.OVAL);
    ring.setColor(blend(accent, 0xFF10131F, 0.16f));
    ring.setStroke(dp(1), blend(accent, 0xFF10131F, 0.55f));
    addToPlaylist.setBackground(
        new android.graphics.drawable.RippleDrawable(
            ColorStateList.valueOf(blend(accent, Color.WHITE, 0.3f)), ring, null));
    addToPlaylist.setImageTintList(ColorStateList.valueOf(accent));
    LinearLayout.LayoutParams addParams = new LinearLayout.LayoutParams(dp(48), dp(48));
    addParams.setMarginStart(dp(12));
    titleRow.addView(addToPlaylist, addParams);
    box.addView(titleRow);
    expandedSeek = playbackSeek(true);
    box.addView(expandedSeek, new LinearLayout.LayoutParams(-1, dp(48)));
    expandedTime = text("", 12, MUTED);
    box.addView(expandedTime);
    LinearLayout controls = row();
    controls.setPadding(0, dp(12), 0, dp(20));
    expandedShuffle =
        iconButton(R.drawable.ic_shuffle, tr("Losowo", "Shuffle"), this::toggleShuffle);
    expandedRepeat =
        iconButton(R.drawable.ic_repeat, tr("Powtarzanie", "Repeat"), this::toggleRepeat);
    expandedPlay = iconButton(R.drawable.ic_play, tr("Odtwórz", "Play"), this::togglePlayback);
    expandedPlay.setBackground(ripple(accent, 36));
    expandedPlay.setImageTintList(ColorStateList.valueOf(0xFF10131F));
    addWeighted(controls, expandedShuffle);
    addWeighted(
        controls,
        iconButton(R.drawable.ic_previous, tr("Poprzedni", "Previous"), this::previousTrack));
    controls.addView(expandedPlay, new LinearLayout.LayoutParams(dp(72), dp(72)));
    addWeighted(controls, iconButton(R.drawable.ic_next, tr("Następny", "Next"), this::nextTrack));
    addWeighted(controls, expandedRepeat);
    box.addView(controls);
    // The queue continues right below the controls: swiping up reveals it at once.
    playerQueue = column();
    box.addView(playerQueue);
    playerQueueKey = "";
    renderPlayerQueue();
    ScrollView scroll = new ScrollView(this);
    scroll.setBackground(
        new GradientDrawable(
            GradientDrawable.Orientation.TOP_BOTTOM,
            new int[] {blend(accent, 0xFF10131F, 0.22f), 0xFF10131F}));
    scroll.setFillViewport(true);
    scroll.addView(box);
    configureScreen(playerDialog.getWindow());
    applyScreenInsets(scroll, 0, 0);
    playerDialog.setContentView(scroll);
    playerDialog.setOnDismissListener(
        d -> {
          expandedDragging = false;
          expandedArtKey = "";
          playerQueue = null;
        });
    playerDialog.show();
    configureScreen(playerDialog.getWindow());
    scroll.requestApplyInsets();
    expandedArtKey = "__reset__";
    updatePlayer();
  }

  private void playerOptions(View anchor) {
    if (controller == null || controller.getCurrentMediaItem() == null) return;
    JSONObject track = Track.json(controller.getCurrentMediaItem());
    PopupMenu popup = new PopupMenu(this, anchor);
    popup.getMenu().add(0, 0, 0, tr("Dodaj do playlisty", "Add to playlist"));
    popup.getMenu().add(0, 1, 1, tr("Otwórz artystę / kanał", "Open artist / channel"));
    popup.getMenu().add(0, 2, 2, tr("Otwórz kartę kolejki", "Open queue tab"));
    popup.setOnMenuItemClickListener(
        item -> {
          switch (item.getItemId()) {
            case 0:
              saveToPlaylist(track);
              break;
            case 1:
              playerDialog.dismiss();
              openArtist(track);
              break;
            default:
              openQueueTab();
          }
          return true;
        });
    popup.show();
  }

  private void openQueueTab() {
    if (playerDialog != null) playerDialog.dismiss();
    tab = 3;
    playlist = "";
    artistTrack = null;
    renderPage();
    pageScroll.scrollTo(0, 0);
  }

  /**
   * Below the full player: the queue first, then the suggestions that continue playback
   * after it. Both refresh whenever they change and both accept drag & drop.
   */
  private void renderPlayerQueue() {
    if (playerQueue == null || controller == null) return;
    playerQueueKey = queueKey();
    playerQueue.removeAllViews();
    int start = Math.max(0, controller.getCurrentMediaItemIndex() + 1);
    int count = Math.max(0, controller.getMediaItemCount() - start);
    JSONArray suggestions = new JSONArray();
    for (JSONObject t : PlaybackService.recommendations) {
      if (suggestions.length() >= 10) break;
      suggestions.put(t);
    }

    playerQueue.addView(
        playerSectionHeader(
            count > 0
                ? tr("Następne w kolejce", "Up next") + "  ·  " + count
                : tr("Następne w kolejce", "Up next"),
            R.drawable.ic_queue,
            tr("Otwórz kartę kolejki", "Open queue tab"),
            this::openQueueTab));
    if (count > 0) {
      LinearLayout list = column();
      list.setTag("player-queue");
      playerQueue.addView(list);
      dropZone(list, ZONE_QUEUE, start);
      appendQueueRows(list, start, queueOrderKey());
    } else if (suggestions.length() > 0) {
      playerQueue.addView(emptyQueueDropZone(start));
    } else {
      playerQueue.addView(text(tr("Kolejka jest pusta.", "The queue is empty."), 13, MUTED));
    }

    LinearLayout suggestionsHeader =
        playerSectionHeader(
            tr("Dla Ciebie", "For you"),
            R.drawable.ic_repeat,
            tr("Odśwież propozycje", "Refresh suggestions"),
            () -> {
              if (PlaybackService.active != null)
                PlaybackService.active.refreshRecommendations(true);
              toast(tr("Szukam propozycji…", "Looking for suggestions…"));
            });
    suggestionsHeader.setPadding(0, dp(20), 0, dp(4));
    playerQueue.addView(suggestionsHeader);
    if (suggestions.length() > 0) {
      playerQueue.addView(
          text(tr("Zagrają, gdy skończy się kolejka.", "They play when the queue ends."), 12, MUTED));
      LinearLayout suggestionList = column();
      suggestionList.setTag("player-suggestions");
      playerQueue.addView(suggestionList);
      dropZone(suggestionList, ZONE_SUGGESTIONS, 0);
      appendSuggestionRows(suggestionList, suggestions);
    } else {
      String message = suggestionMessage();
      playerQueue.addView(
          text(
              message.isEmpty() ? tr("Brak propozycji.", "No suggestions yet.") : message,
              13,
              MUTED));
    }
  }

  private LinearLayout playerSectionHeader(String label, int icon, String action, Runnable run) {
    LinearLayout header = row();
    header.setPadding(0, dp(8), 0, dp(4));
    TextView title = text(label, 17, Color.WHITE);
    title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
    header.addView(iconButton(icon, action, run), new LinearLayout.LayoutParams(dp(48), dp(48)));
    return header;
  }

  private void updateExpandedPlayer(JSONObject track, long duration, long position) {
    if (playerDialog == null || !playerDialog.isShowing()) return;
    if (playerQueue != null && dragFrom < 0 && !queueKey().equals(playerQueueKey))
      renderPlayerQueue();
    expandedTitle.setText(track.optString("title"));
    expandedArtist.setText(Track.artist(track));
    String key = track.optString("thumbnail_url");
    if (!key.equals(expandedArtKey)) {
      expandedArtKey = key;
      Glide.with(this)
          .load(key)
          .placeholder(R.drawable.music_crow)
          .error(R.drawable.music_crow)
          .transition(DrawableTransitionOptions.withCrossFade(motionEnabled() ? 320 : 0))
          .into(expandedArt);
    }
    expandedPlay.setImageResource(playbackRequested() ? R.drawable.ic_pause : R.drawable.ic_play);
    expandedPlay.setContentDescription(
        playbackRequested() ? tr("Wstrzymaj", "Pause") : tr("Odtwórz", "Play"));
    expandedShuffle.setImageTintList(
        ColorStateList.valueOf(controller.getShuffleModeEnabled() ? accent : MUTED));
    expandedShuffle.setSelected(controller.getShuffleModeEnabled());
    expandedRepeat.setImageResource(
        controller.getRepeatMode() == Player.REPEAT_MODE_ONE
            ? R.drawable.ic_repeat_one
            : R.drawable.ic_repeat);
    expandedRepeat.setImageTintList(
        ColorStateList.valueOf(
            controller.getRepeatMode() == Player.REPEAT_MODE_OFF ? MUTED : accent));
    expandedRepeat.setContentDescription(
        tr("Powtarzanie: ", "Repeat: ")
            + (controller.getRepeatMode() == Player.REPEAT_MODE_ONE
                ? tr("utwór", "one")
                : controller.getRepeatMode() == Player.REPEAT_MODE_ALL
                    ? tr("wszystko", "all")
                    : tr("wyłączone", "off")));
    expandedSeek.setEnabled(duration > 0 && controller.isCurrentMediaItemSeekable());
    if (!expandedDragging)
      expandedSeek.setProgress(
          duration > 0 ? (int) (position * 1000 / duration) : 0, motionEnabled());
    expandedTime.setText(time.getText());
  }

  private <T> void runTask(Callable<T> work, Consumer<T> success, Consumer<String> failure) {
    CrowApp.IO.execute(
        () -> {
          try {
            T result = work.call();
            handler.post(
                () -> {
                  if (!isFinishing() && !isDestroyed()) success.accept(result);
                });
          } catch (Exception error) {
            String message = error.getMessage();
            if (message == null) message = tr("Operacja nie powiodła się", "Operation failed");
            if (message.contains("yt_dlp") || message.contains("http") || message.length() > 450)
              message =
                  tr(
                      "Nie udało się pobrać danych. Sprawdź połączenie i dostępność utworu.",
                      "Could not load data. Check your connection and track availability.");
            final String safe = message;
            handler.post(
                () -> {
                  if (!isFinishing() && !isDestroyed()) failure.accept(safe);
                });
          }
        });
  }

  private void mutate(String action, JSONObject args, Runnable done) {
    runTask(() -> app.call(action, args), result -> done.run(), this::showError);
  }

  private void prompt(String title, String initial, Consumer<String> submit) {
    EditText input = new EditText(this);
    input.setSingleLine(true);
    input.setText(initial);
    new AlertDialog.Builder(this)
        .setTitle(title)
        .setView(input)
        .setNegativeButton(tr("Anuluj", "Cancel"), null)
        .setPositiveButton(
            "OK",
            (d, w) -> {
              String value = input.getText().toString().trim();
              if (!value.isEmpty()) submit.accept(value);
            })
        .show();
  }

  private void confirm(String title, String message, Runnable action) {
    new AlertDialog.Builder(this)
        .setTitle(title)
        .setMessage(message)
        .setNegativeButton(tr("Anuluj", "Cancel"), null)
        .setPositiveButton(tr("Potwierdź", "Confirm"), (d, w) -> action.run())
        .show();
  }

  private void showError(String message) {
    new AlertDialog.Builder(this)
        .setTitle(tr("Muzyczna Wrona", "Music Crow"))
        .setMessage(message)
        .setPositiveButton("OK", null)
        .show();
  }

  private void toast(String message) {
    Toast.makeText(this, message, Toast.LENGTH_LONG).show();
  }

  private int dp(int value) {
    return (int) (value * getResources().getDisplayMetrics().density);
  }

  private String clock(long ms) {
    return String.format(Locale.ROOT, "%d:%02d", ms / 60000, ms / 1000 % 60);
  }

  private LinearLayout column() {
    LinearLayout view = new LinearLayout(this);
    view.setOrientation(LinearLayout.VERTICAL);
    return view;
  }

  private LinearLayout row() {
    LinearLayout view = new LinearLayout(this);
    view.setOrientation(LinearLayout.HORIZONTAL);
    view.setGravity(Gravity.CENTER_VERTICAL);
    return view;
  }

  private GradientDrawable background(int color) {
    GradientDrawable shape = new GradientDrawable();
    shape.setColor(color);
    shape.setCornerRadius(dp(14));
    return shape;
  }

  private LinearLayout card() {
    LinearLayout view = column();
    view.setPadding(dp(12), dp(12), dp(12), dp(12));
    view.setBackground(ripple(SURFACE, 14));
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
    params.setMargins(0, dp(3), 0, dp(5));
    view.setLayoutParams(params);
    return view;
  }

  private TextView text(String value, int size, int color) {
    TextView view = new TextView(this);
    view.setText(value);
    view.setTextSize(size);
    view.setTextColor(color);
    view.setEllipsize(TextUtils.TruncateAt.END);
    view.setIncludeFontPadding(false);
    view.setPadding(0, dp(4), 0, dp(4));
    return view;
  }

  private void section(String title) {
    TextView heading = text(title, 17, Color.WHITE);
    heading.setTypeface(null, Typeface.BOLD);
    heading.setPadding(0, dp(18), 0, dp(8));
    content.addView(heading);
  }

  private Button button(String label, Runnable action) {
    Button view = new Button(this);
    view.setText(label);
    view.setAllCaps(false);
    view.setTextSize(14);
    view.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    view.setTextColor(0xFFE3DEFA);
    view.setBackground(ripple(0xFF292C37, 12));
    view.setMinHeight(dp(48));
    view.setMinimumHeight(dp(48));
    view.setPadding(dp(16), dp(12), dp(16), dp(12));
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
    params.setMargins(0, dp(5), 0, dp(5));
    view.setLayoutParams(params);
    view.setOnClickListener(v -> action.run());
    pressFeedback(view);
    return view;
  }

  private Button primaryButton(String label, Runnable action) {
    Button view = button(label, action);
    view.setBackground(ripple(accent, 14));
    view.setTextColor(0xFF10131F);
    return view;
  }

  private ImageButton iconButton(int icon, String label, Runnable action) {
    ImageButton view = new ImageButton(this);
    view.setImageResource(icon);
    view.setImageTintList(ColorStateList.valueOf(Color.WHITE));
    view.setBackground(ripple(Color.TRANSPARENT, 24));
    view.setPadding(dp(12), dp(12), dp(12), dp(12));
    view.setMinimumHeight(dp(48));
    view.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
    view.setContentDescription(label);
    view.setOnClickListener(v -> action.run());
    pressFeedback(view);
    return view;
  }

  private Drawable ripple(int color, int radius) {
    GradientDrawable fill = background(color);
    fill.setCornerRadius(dp(radius));
    GradientDrawable mask = background(Color.WHITE);
    mask.setCornerRadius(dp(radius));
    return new RippleDrawable(ColorStateList.valueOf(0x30FFFFFF), fill, mask);
  }

  private boolean motionEnabled() {
    return ValueAnimator.areAnimatorsEnabled();
  }

  private void pressFeedback(View view) {
    view.setOnTouchListener(
        (target, event) -> {
          if (motionEnabled()) {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
              target.animate().scaleX(0.96f).scaleY(0.96f).setDuration(90).start();
            } else if (event.getActionMasked() == MotionEvent.ACTION_UP
                || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
              target
                  .animate()
                  .scaleX(1f)
                  .scaleY(1f)
                  .setDuration(160)
                  .setInterpolator(new android.view.animation.DecelerateInterpolator())
                  .start();
            }
          }
          return false;
        });
  }

  private void animatePageEntrance() {
    content.animate().cancel();
    content.setAlpha(1f);
    content.setTranslationY(0f);
    if (!motionEnabled()) return;
    final int request = generation;
    content.setAlpha(0f);
    content.setTranslationY(dp(12));
    content.post(
        () -> {
          if (request != generation || isDestroyed()) return;
          content
              .animate()
              .alpha(1f)
              .translationY(0f)
              .setDuration(220)
              .setInterpolator(new android.view.animation.DecelerateInterpolator())
              .start();
        });
  }

  private int blend(int foreground, int back, float amount) {
    return Color.rgb(
        (int) (Color.red(foreground) * amount + Color.red(back) * (1 - amount)),
        (int) (Color.green(foreground) * amount + Color.green(back) * (1 - amount)),
        (int) (Color.blue(foreground) * amount + Color.blue(back) * (1 - amount)));
  }

  private void tintSeek(SeekBar bar) {
    bar.setProgressTintList(ColorStateList.valueOf(accent));
    bar.setThumbTintList(ColorStateList.valueOf(accent));
    bar.setProgressBackgroundTintList(ColorStateList.valueOf(0xFF343B52));
  }

  private void styleSwitch(Switch toggle) {
    toggle.setMinHeight(dp(56));
    toggle.setTextSize(14);
    toggle.setPadding(0, dp(8), dp(4), dp(8));
    toggle.setThumbTintList(
        new ColorStateList(
            new int[][] {new int[] {android.R.attr.state_checked}, new int[] {}},
            new int[] {accent, 0xFFB1B8CD}));
    toggle.setTrackTintList(
        new ColorStateList(
            new int[][] {new int[] {android.R.attr.state_checked}, new int[] {}},
            new int[] {blend(accent, SURFACE, 0.4f), 0xFF343B52}));
  }

  private void emptyState(String title, String detail) {
    LinearLayout box = card();
    box.setPadding(dp(20), dp(24), dp(20), dp(24));
    TextView heading = text(title, 18, Color.WHITE);
    heading.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
    box.addView(heading);
    box.addView(text(detail, 14, MUTED));
    content.addView(box);
  }

  private void addWeighted(LinearLayout row, View view) {
    if (view instanceof Button) {
      ((Button) view).setMinWidth(0);
      view.setPadding(0, 0, 0, 0);
    }
    LinearLayout.LayoutParams params =
        new LinearLayout.LayoutParams(0, view instanceof ImageButton ? dp(56) : -2, 1);
    params.setMargins(dp(3), dp(4), dp(3), dp(4));
    row.addView(view, params);
  }

  private ImageView art(String value, boolean encoded) {
    ImageView image = new ImageView(this);
    image.setScaleType(ImageView.ScaleType.CENTER_CROP);
    image.setBackground(background(0xFF2B3048));
    image.setClipToOutline(true);
    image.setImageResource(R.drawable.music_crow);
    if (!value.isEmpty()) {
      Object model = value;
      try {
        if (encoded) model = android.util.Base64.decode(value, android.util.Base64.DEFAULT);
        Glide.with(this)
            .load(model)
            .placeholder(R.drawable.music_crow)
            .error(R.drawable.music_crow)
            .into(image);
      } catch (Exception ignored) {
      }
    }
    return image;
  }
}
