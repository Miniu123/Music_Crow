# Google Drive — wspólna kopia Android / PC

Kod Androida korzysta z Google Identity Authorization API oraz dokładnie tego
samego zakresu `https://www.googleapis.com/auth/drive.appdata`, nazwy
`music-crow-config.json` i formatu `music-crow-backup` v1 co desktop.

## Jednorazowa konfiguracja właściciela aplikacji

25 października 2026 utworzono klienta **Music Crow Android — debug** w projekcie
**minecraft** (`first-torus-363514`, numer `135151353988`), wspólnym z klientem PC.
Identyfikator klienta Android:
`135151353988-7kitt8r19ijt7j6tckrg8sov0t10999c.apps.googleusercontent.com`.
Pakiet i SHA-1 odpowiadają wartościom poniżej. Potwierdzono również istniejący
zakres `drive.appdata` oraz zewnętrzny, produkcyjny tryb ekranu zgody.
Pozostaje test logowania i kopii z prawdziwego konta na telefonie.

W Google Cloud wybierz **ten sam projekt, w którym istnieje klient OAuth wersji PC**.
Osobny projekt Androida nie zobaczy prywatnego folderu kopii aplikacji PC.

1. Otwórz **Google Auth Platform → Clients → Create client**.
2. Wybierz typ **Android**, nazwę np. **Music Crow Android — debug**.
3. Wpisz nazwę pakietu:
   `io.github.miniu123.musiccrow`
4. Dla APK zbudowanego w tym środowisku wpisz SHA-1 certyfikatu:
   `6D:04:CE:C8:8A:FE:D6:00:FE:55:72:3C:5F:D7:C6:C0:A0:64:1A:3C`
5. Utwórz klienta. Google Drive API musi być włączone w tym projekcie, a zakres
   `drive.appdata` dodany do konfiguracji zgody. W trybie Testing konto telefonu
   musi znajdować się na liście testowych użytkowników.
6. Na telefonie wybierz **Ustawienia → Google Drive → Zaloguj / Przywróć kopię…**,
   wybierz to samo konto Google co na PC, zaakceptuj dostęp do kopii i wybierz
   istniejącą kopię. Aplikacja pokaże liczbę playlist i utworów przed przywróceniem.

Klient Android identyfikuje aplikację pakietem i certyfikatem. **Nie trzeba
kopiować desktopowego client_secret ani pliku OAuth do APK.** Klucze użytkownika
nie są przechowywane w kopii. Token dostępu uzyskiwany z Google Play services
pozostaje tylko w pamięci procesu.

SHA-1 powyżej dotyczy obecnego lokalnego klucza debug. Inny komputer może mieć
inny klucz. Zweryfikuj go poleceniem:

```sh
./gradlew :app:signingReport
```

Przed publikacją trzeba dodać klienta Android dla certyfikatu wersji release
(lub certyfikatu App Signing używanego przez Google Play). Kluczy podpisywania
nie dodawaj do repozytorium.

## Zachowanie kopii

- Przywracanie łączy playlisty. Różne playlisty o tej samej nazwie otrzymują
  przyrostek `(Google Drive)`. Powtórny import tej samej playlisty jej nie dubluje.
- Przywracanie ustawień jest częścią potwierdzanej operacji. Przed zmianą powstaje
  lokalna kopia awaryjna w prywatnym folderze aplikacji `files/recovery/`.
- Historia jest opcjonalna przy zapisie; przy przywracaniu nie sumujemy tych
  samych odtworzeń z dwóch urządzeń.
- Dla każdego konta zapamiętywany jest identyfikator pliku i jego suma MD5.
  Nieznana, nowsza lub niejednoznaczna kopia blokuje zapis do czasu przywrócenia.
- Samo pobranie kopii i anulowanie podglądu nie daje zgody na jej nadpisanie.
- Automatyczny zapis odbywa się po zmianach oraz okresowo podczas działania
  procesu aplikacji. Po zatrzymaniu procesu nie ma osobnego zadania WorkManager.
- To kopia z ręcznym przywracaniem, nie synchronizacja na żywo. Kontrola sumy
  przed zapisem nie eliminuje wyścigu dwóch jednoczesnych zapisów.
- Audio, cache, tokeny i konfiguracja Google nie są wysyłane. Lokalne pliki audio
  z PC/telefonu trzeba przenieść osobno; uprawnienia `content://` są lokalne dla
  urządzenia. Linki YouTube/SoundCloud są przenośne.

## Test końcowy z prawdziwym kontem

1. Na PC utwórz playlistę z utworem online i zapisz kopię.
2. Na Androidzie zaloguj się, przywróć ją i sprawdź odtwarzanie utworu.
3. Dodaj na Androidzie drugą playlistę, wykonaj kopię i przywróć ją na PC.
4. Zmień kopię na PC, potem spróbuj zapisu z Androida bez przywracania: aplikacja
   powinna zablokować zapis i poprosić o przywrócenie.

Ten test wymaga poprawnie skonfigurowanego klienta Android i zgody użytkownika.
Testy protokołu w repozytorium używają izolowanych danych testowych i nie
potwierdzają dostępu do prawdziwego konta.

Dokumentacja Google:
- https://developers.google.com/identity/authorization/android/authorize-access
- https://developers.google.com/workspace/drive/api/guides/appdata
