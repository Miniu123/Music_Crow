package io.github.miniu123.musiccrow;

import static org.junit.Assert.*;

import android.content.Context;
import android.content.ContextWrapper;
import android.content.SharedPreferences;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class DriveProtocolTest {
  private FakeDrive drive;
  private static final byte[] DATA = "test-backup".getBytes(StandardCharsets.UTF_8);

  static class FakeDrive extends DriveClient {
    final List<JSONObject> files = new ArrayList<>();
    int writes;

    FakeDrive(Context context) {
      super(context, "test-token");
      accountId = "test-account";
      email = "test@example.invalid";
    }

    @Override
    void account() {}

    @Override
    List<JSONObject> list() {
      return files;
    }

    @Override
    Response request(String method, String url, byte[] payload, Map<String, String> headers)
        throws Exception {
      if (!method.equals("GET")) writes++;
      if (method.equals("PUT"))
        return new Response(
            CrowApp.obj("id", "new-id").toString().getBytes(StandardCharsets.UTF_8), null);
      return new Response(
          "{}".getBytes(StandardCharsets.UTF_8), "https://www.googleapis.com/upload/session");
    }
  }

  @Before
  public void setup() {
    Context target = InstrumentationRegistry.getInstrumentation().getTargetContext();
    Context isolated =
        new ContextWrapper(target) {
          @Override
          public SharedPreferences getSharedPreferences(String name, int mode) {
            return super.getSharedPreferences("test-" + name, mode);
          }
        };
    drive = new FakeDrive(isolated);
    drive.preferences.edit().clear().commit();
  }

  @After
  public void cleanup() {
    drive.preferences.edit().clear().commit();
  }

  private JSONObject file(String id, String checksum) {
    return CrowApp.obj("id", id, "name", DriveClient.NAME, "md5Checksum", checksum);
  }

  private void conflict() throws Exception {
    try {
      drive.upload(DATA);
      fail("Expected conflict");
    } catch (java.io.IOException error) {
      assertEquals(DriveClient.CONFLICT, error.getMessage());
    }
    assertEquals(0, drive.writes);
  }

  @Test
  public void freshInstallationCannotOverwriteExistingBackup() throws Exception {
    drive.files.add(file("existing", "remote"));
    conflict();
  }

  @Test
  public void differentAccountCannotReuseAcknowledgement() throws Exception {
    drive.files.add(file("existing", "remote"));
    drive
        .preferences
        .edit()
        .putString("another-account.id", "existing")
        .putString("another-account.checksum", "remote")
        .commit();
    conflict();
  }

  @Test
  public void changedRemoteChecksumBlocksUpload() throws Exception {
    drive.files.add(file("existing", "newer"));
    drive
        .preferences
        .edit()
        .putString("test-account.id", "existing")
        .putString("test-account.checksum", "older")
        .commit();
    conflict();
  }

  @Test
  public void duplicateSharedFilesBlockUpload() throws Exception {
    drive.files.add(file("existing", "same"));
    drive.files.add(file("other", "same"));
    drive
        .preferences
        .edit()
        .putString("test-account.id", "existing")
        .putString("test-account.checksum", "same")
        .commit();
    conflict();
  }

  @Test
  public void acknowledgedUnchangedBackupDoesNotUpload() throws Exception {
    JSONObject file = file("existing", DriveClient.md5(DATA));
    drive.files.add(file);
    drive.acknowledge(file, DATA);
    drive.upload(DATA);
    assertEquals(0, drive.writes);
  }

  @Test
  public void emptyAccountCreatesSharedBackup() throws Exception {
    drive.upload(DATA);
    assertEquals(2, drive.writes);
    assertEquals("new-id", drive.preferences.getString("test-account.id", ""));
  }

  @Test
  public void legacyRestoreDoesNotAcknowledgeSharedBackup() throws Exception {
    JSONObject file = file("legacy", "checksum");
    file.put("name", "music-crow-old-device.json");
    drive.acknowledge(file, DATA);
    assertFalse(drive.preferences.contains("test-account.id"));
  }

  @Test
  public void readLimitRejectsOversizeBeforeReturning() throws Exception {
    try {
      DriveClient.readLimited(new java.io.ByteArrayInputStream(new byte[100]), 50);
      fail("Expected size limit");
    } catch (java.io.IOException expected) {
      assertTrue(expected.getMessage().contains("large"));
    }
  }
}
