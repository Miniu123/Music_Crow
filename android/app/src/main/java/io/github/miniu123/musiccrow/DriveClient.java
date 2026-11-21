package io.github.miniu123.musiccrow;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

class DriveClient {
  static final int MAX = 40 * 1024 * 1024;
  static final String SCOPE = "https://www.googleapis.com/auth/drive.appdata";
  static final String NAME = "music-crow-config.json";
  static final String API = "https://www.googleapis.com/drive/v3";
  static final String CONFLICT =
      "Na Dysku jest nieznana lub nowsza kopia. Najpierw ją przywróć. / Drive has a newer or"
          + " unknown backup. Restore it first.";
  final String token;
  final SharedPreferences preferences;
  String accountId;
  String email;

  DriveClient(Context context, String token) {
    this.token = token;
    preferences = context.getSharedPreferences("drive", Context.MODE_PRIVATE);
  }

  static final class Response {
    final byte[] body;
    final String location;

    Response(byte[] body, String location) {
      this.body = body;
      this.location = location;
    }

    JSONObject json() throws JSONException {
      return new JSONObject(new String(body, StandardCharsets.UTF_8));
    }
  }

  Response request(String method, String address, byte[] payload, Map<String, String> headers)
      throws Exception {
    URL url = new URL(address);
    if (!url.getProtocol().equals("https")
        || !url.getHost().equals("www.googleapis.com")
        || url.getUserInfo() != null) throw new IOException("Invalid Drive address");
    HttpURLConnection connection = (HttpURLConnection) url.openConnection();
    try {
      connection.setInstanceFollowRedirects(false);
      connection.setConnectTimeout(15000);
      connection.setReadTimeout(30000);
      connection.setRequestMethod(method);
      connection.setRequestProperty("Authorization", "Bearer " + token);
      if (headers != null)
        for (Map.Entry<String, String> entry : headers.entrySet())
          connection.setRequestProperty(entry.getKey(), entry.getValue());
      if (payload != null) {
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(payload.length);
        try (OutputStream out = connection.getOutputStream()) {
          out.write(payload);
        }
      }
      int status = connection.getResponseCode();
      if (status == 401) throw new IOException("Zaloguj się ponownie / Sign in again");
      if (status == 403)
        throw new IOException(
            "Brak dostępu. Sprawdź zgodę i konfigurację Google OAuth Android. / Access denied."
                + " Check Google OAuth configuration.");
      if (status < 200 || status >= 300) throw new IOException("Google Drive HTTP " + status);
      if (connection.getContentLengthLong() > MAX)
        throw new IOException("Kopia przekracza 40 MB / Backup exceeds 40 MB");
      try (InputStream input = connection.getInputStream()) {
        return new Response(readLimited(input, MAX), connection.getHeaderField("Location"));
      }
    } finally {
      connection.disconnect();
    }
  }

  static byte[] readLimited(InputStream input, int maximum) throws IOException {
    if (input == null) throw new IOException("Brak pliku / Missing file");
    ByteArrayOutputStream output = new ByteArrayOutputStream();
    byte[] buffer = new byte[16384];
    int count;
    while ((count = input.read(buffer)) != -1) {
      if (output.size() + count > maximum)
        throw new IOException("Plik jest za duży / File too large");
      output.write(buffer, 0, count);
    }
    return output.toByteArray();
  }

  void account() throws Exception {
    JSONObject user =
        request("GET", API + "/about?fields=user(permissionId,emailAddress)", null, null)
            .json()
            .getJSONObject("user");
    accountId = user.getString("permissionId");
    email = user.optString("emailAddress");
    preferences.edit().putString("email", email).apply();
  }

  List<JSONObject> list() throws Exception {
    List<JSONObject> result = new ArrayList<>();
    String page = "";
    for (int i = 0; i < 20; i++) {
      String address =
          API
              + "/files?spaces=appDataFolder&q=trashed%3Dfalse&pageSize=100&fields=nextPageToken%2Cfiles(id%2Cname%2CmodifiedTime%2Csize%2Cmd5Checksum)&orderBy=modifiedTime%20desc";
      if (!page.isEmpty()) address += "&pageToken=" + URLEncoder.encode(page, "UTF-8");
      JSONObject response = request("GET", address, null, null).json();
      JSONArray files = response.optJSONArray("files");
      for (int j = 0; files != null && j < files.length(); j++) {
        JSONObject file = files.getJSONObject(j);
        String name = file.optString("name");
        if (name.startsWith("music-crow-") && name.endsWith(".json")) result.add(file);
      }
      page = response.optString("nextPageToken");
      if (page.isEmpty()) return result;
    }
    throw new IOException("Zbyt wiele kopii / Too many backups");
  }

  byte[] download(JSONObject selected) throws Exception {
    String id = selected.getString("id");
    JSONObject verified = null;
    for (JSONObject file : list()) if (file.optString("id").equals(id)) verified = file;
    if (verified == null || verified.optLong("size") > MAX)
      throw new IOException("Nieprawidłowa kopia / Invalid backup");
    return request(
            "GET", API + "/files/" + URLEncoder.encode(id, "UTF-8") + "?alt=media", null, null)
        .body;
  }

  void acknowledge(JSONObject file, byte[] raw) throws Exception {
    if (!NAME.equals(file.optString("name"))) return;
    if (accountId == null) throw new IOException("Missing account identity");
    preferences
        .edit()
        .putString(accountId + ".id", file.getString("id"))
        .putString(accountId + ".checksum", md5(raw))
        .apply();
  }

  synchronized void upload(byte[] payload) throws Exception {
    if (accountId == null) account();
    List<JSONObject> matches = new ArrayList<>();
    for (JSONObject file : list()) if (NAME.equals(file.optString("name"))) matches.add(file);
    String expectedId = preferences.getString(accountId + ".id", "");
    String expectedChecksum = preferences.getString(accountId + ".checksum", "");
    if (!matches.isEmpty()
        && (matches.size() != 1
            || !matches.get(0).optString("id").equals(expectedId)
            || expectedChecksum.isEmpty()
            || !matches.get(0).optString("md5Checksum").equals(expectedChecksum)))
      throw new IOException(CONFLICT);
    String checksum = md5(payload);
    if (matches.size() == 1 && checksum.equals(expectedChecksum)) return;
    JSONObject metadata = new JSONObject();
    String method = "POST";
    String address = "https://www.googleapis.com/upload/drive/v3/files";
    if (matches.isEmpty())
      metadata =
          CrowApp.obj(
              "name",
              NAME,
              "parents",
              new JSONArray().put("appDataFolder"),
              "mimeType",
              "application/json");
    else {
      method = "PATCH";
      address += "/" + URLEncoder.encode(matches.get(0).getString("id"), "UTF-8");
    }
    address += "?uploadType=resumable&fields=id%2Cname%2Cmd5Checksum";
    Map<String, String> headers = new HashMap<>();
    headers.put("Content-Type", "application/json; charset=UTF-8");
    headers.put("X-Upload-Content-Type", "application/json");
    headers.put("X-Upload-Content-Length", String.valueOf(payload.length));
    Response session =
        request(method, address, metadata.toString().getBytes(StandardCharsets.UTF_8), headers);
    if (session.location == null) throw new IOException("Missing upload session");
    JSONObject saved =
        request(
                "PUT",
                session.location,
                payload,
                Collections.singletonMap("Content-Type", "application/json"))
            .json();
    preferences
        .edit()
        .putString(accountId + ".id", saved.getString("id"))
        .putString(accountId + ".checksum", checksum)
        .apply();
  }

  static String md5(byte[] raw) throws Exception {
    byte[] digest = MessageDigest.getInstance("MD5").digest(raw);
    StringBuilder out = new StringBuilder();
    for (byte b : digest) out.append(String.format(Locale.ROOT, "%02x", b & 255));
    return out.toString();
  }
}
