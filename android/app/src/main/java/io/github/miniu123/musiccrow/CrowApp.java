package io.github.miniu123.musiccrow;

import android.app.Application;
import android.os.Handler;
import android.os.Looper;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.util.concurrent.*;
import org.json.*;

public final class CrowApp extends Application {
  public static CrowApp instance;
  public static final ExecutorService IO = Executors.newFixedThreadPool(3);
  public static final Handler MAIN = new Handler(Looper.getMainLooper());
  public volatile JSONObject state = new JSONObject();
  public volatile String initializationError;
  private final Runnable autoBackup =
      new Runnable() {
        public void run() {
          DriveSync.automatic();
          MAIN.postDelayed(this, 300000);
        }
      };
  private final CountDownLatch ready = new CountDownLatch(1);
  public static final String CHANGED = "io.github.miniu123.musiccrow.CHANGED";

  @Override
  public void onCreate() {
    super.onCreate();
    instance = this;
    IO.execute(
        () -> {
          try {
            Python.start(new AndroidPlatform(this));
            Python.getInstance()
                .getModule("crow")
                .callAttr("initialize", getFilesDir().getAbsolutePath());
            state =
                new JSONObject(
                    Python.getInstance()
                        .getModule("crow")
                        .callAttr("dispatch", "state", "{}")
                        .toString());
          } catch (Exception e) {
            initializationError =
                "Nie można otworzyć biblioteki. Dane zostały zachowane. / Cannot open library. Data"
                    + " retained.";
          } finally {
            ready.countDown();
            MAIN.postDelayed(autoBackup, 5000);
          }
        });
  }

  public synchronized String call(String action, JSONObject args) throws Exception {
    ready.await();
    if (initializationError != null) throw new Exception(initializationError);
    String result =
        Python.getInstance()
            .getModule("crow")
            .callAttr("dispatch", action, args.toString())
            .toString();
    if (!action.equals("preview") && !action.equals("recommend") && !action.equals("backup")) {
      state = new JSONObject(result);
      if (!action.equals("state")) {
        sendBroadcast(new android.content.Intent(CHANGED).setPackage(getPackageName()));
        MAIN.removeCallbacks(autoBackup);
        MAIN.postDelayed(autoBackup, 3000);
      }
    }
    return result;
  }

  public String source(String method, Object... args) throws Exception {
    ready.await();
    if (initializationError != null) throw new Exception(initializationError);
    return Python.getInstance().getModule("sources").callAttr(method, args).toString();
  }

  public JSONObject settings() {
    return state.optJSONObject("settings") == null
        ? new JSONObject()
        : state.optJSONObject("settings");
  }

  public static JSONObject obj(Object... values) {
    JSONObject object = new JSONObject();
    try {
      for (int i = 0; i < values.length; i += 2) object.put((String) values[i], values[i + 1]);
    } catch (JSONException e) {
      throw new IllegalArgumentException(e);
    }
    return object;
  }
}
