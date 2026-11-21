package io.github.miniu123.musiccrow;

import android.accounts.Account;
import android.app.Activity;
import android.content.*;
import com.google.android.gms.auth.api.identity.*;
import com.google.android.gms.common.api.Scope;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

final class DriveSync {
  static final int REQUEST = 420;
  static volatile String status = "";
  static final AtomicBoolean uploading = new AtomicBoolean();

  interface Authorized {
    void accept(DriveClient drive);
  }

  static AuthorizationRequest request(Context context) {
    AuthorizationRequest.Builder builder =
        AuthorizationRequest.builder()
            .setRequestedScopes(Collections.singletonList(new Scope(DriveClient.SCOPE)));
    String email =
        context.getSharedPreferences("drive", Context.MODE_PRIVATE).getString("email", "");
    if (!email.isEmpty()) builder.setAccount(new Account(email, "com.google"));
    return builder.build();
  }

  static void authorize(
      Activity activity, Authorized callback, java.util.function.Consumer<String> error) {
    Identity.getAuthorizationClient(activity)
        .authorize(request(activity))
        .addOnSuccessListener(
            result -> {
              if (result.hasResolution()) {
                try {
                  activity.startIntentSenderForResult(
                      result.getPendingIntent().getIntentSender(), REQUEST, null, 0, 0, 0);
                } catch (Exception e) {
                  error.accept("Nie można otworzyć logowania Google / Cannot open Google sign-in");
                }
              } else complete(activity, result, callback, error);
            })
        .addOnFailureListener(
            e ->
                error.accept(
                    "Logowanie Google niedostępne. Zarejestruj klienta OAuth Android dla tej"
                        + " aplikacji w projekcie Google wersji PC. / Register this Android app in"
                        + " the PC app's Google project."));
  }

  static void result(
      Activity activity,
      Intent data,
      Authorized callback,
      java.util.function.Consumer<String> error) {
    try {
      complete(
          activity,
          Identity.getAuthorizationClient(activity).getAuthorizationResultFromIntent(data),
          callback,
          error);
    } catch (Exception e) {
      error.accept("Logowanie anulowane lub nieudane / Sign-in cancelled or failed");
    }
  }

  private static void complete(
      Context context,
      AuthorizationResult result,
      Authorized callback,
      java.util.function.Consumer<String> error) {
    String token = result.getAccessToken();
    if (token == null || !result.getGrantedScopes().contains(DriveClient.SCOPE)) {
      error.accept("Brak zgody na kopie Drive / Drive backup access not granted");
      return;
    }
    CrowApp.IO.execute(
        () -> {
          try {
            DriveClient drive = new DriveClient(context.getApplicationContext(), token);
            drive.account();
            CrowApp.MAIN.post(() -> callback.accept(drive));
          } catch (Exception e) {
            CrowApp.MAIN.post(() -> error.accept(e.getMessage()));
          }
        });
  }

  static void automatic() {
    CrowApp context = CrowApp.instance;
    SharedPreferences prefs = context.getSharedPreferences("drive", Context.MODE_PRIVATE);
    if (!prefs.getBoolean("auto", false)
        || prefs.getString("email", "").isEmpty()
        || !uploading.compareAndSet(false, true)) return;
    Identity.getAuthorizationClient(context)
        .authorize(request(context))
        .addOnSuccessListener(
            result -> {
              if (result.hasResolution() || result.getAccessToken() == null) {
                status = "Otwórz Google Drive i zaloguj się / Open Google Drive and sign in";
                uploading.set(false);
                return;
              }
              CrowApp.IO.execute(
                  () -> {
                    try {
                      byte[] payload =
                          context
                              .call(
                                  "backup",
                                  CrowApp.obj("history", prefs.getBoolean("history", false)))
                              .getBytes(StandardCharsets.UTF_8);
                      DriveClient drive = new DriveClient(context, result.getAccessToken());
                      drive.account();
                      drive.upload(payload);
                      status = "Kopia zapisana / Backup saved";
                    } catch (Exception e) {
                      status = e.getMessage();
                    } finally {
                      uploading.set(false);
                    }
                  });
            })
        .addOnFailureListener(
            error -> {
              status = "Automatyczna kopia czeka na logowanie / Automatic backup needs sign-in";
              uploading.set(false);
            });
  }

  static void disconnect(
      Context context, Runnable done, java.util.function.Consumer<String> error) {
    Identity.getAuthorizationClient(context)
        .revokeAccess(
            RevokeAccessRequest.builder()
                .setScopes(Collections.singletonList(new Scope(DriveClient.SCOPE)))
                .build())
        .addOnSuccessListener(
            unused -> {
              context.getSharedPreferences("drive", Context.MODE_PRIVATE).edit().clear().apply();
              status = "";
              done.run();
            })
        .addOnFailureListener(
            e -> error.accept("Nie udało się odłączyć Google / Could not disconnect Google"));
  }
}
