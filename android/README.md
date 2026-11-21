# Music Crow — Android 0.9.1

Natywny port Muzycznej Wrony na Androida. Interfejs Java/Android, odtwarzanie
Media3, Python 3.14 przez Chaquopy, yt-dlp do źródeł online. Kod desktopu
pozostaje osobnym projektem. Android korzysta z oryginalnego logo i przeniesionych
funkcji rankingu z `core/recommendations.py`.

## Funkcje

- Import YouTube Music: **Playlisty → Importuj z YouTube Music**. Wklej link
  skopiowany przez **Udostępnij → Kopiuj link** w YouTube Music, wczytaj playlistę
  i potwierdź nazwę oraz liczbę dostępnych utworów. Import wymaga playlisty publicznej
  lub niepublicznej (dostępnej z linku); prywatne listy, polubione i radio nie są
  importowane przez logowanie Google Drive. Zapisuje listę utworów, nie pliki audio.
  Link utworu z parametrem playlisty wczytuje całą listę od początku. Niedostępne
  pozycje zwrócone przez źródło są pomijane i zliczane. Istniejące playlisty nie
  są nadpisywane ani automatycznie łączone. Limit: 10000 utworów.

- Propozycje domyślnie pomijają remiksy, bootlegi, mashupy, nightcore i zmiany
  tempa; wybranie remiksu pozwala proponować podobne wersje. Dopasowanie wykonawcy
  opiera się na jego metadanych i jawnych oznaczeniach współpracy.
- Powrót do aplikacji nie przerywa trwającego wyszukiwania propozycji. Ranking
  od razu uwzględnia zachowane odkrycia; kolejne partie wyników trafiają do cache
  na bieżąco. Usunięte propozycje nie wracają w spóźnionej partii tych samych URL.
- Przy pustej zwykłej kolejce przygotowywane jest audio pierwszej propozycji
  (jeśli przygotowywanie jest włączone). Ręcznie dodany utwór ma pierwszeństwo.
  Zakładka kolejki pokazuje stan szukania i przygotowania, brak wyników lub błąd
  połączenia. Pauza działa także podczas buforowania; wznowienie po końcu nagrania
  pozostaje przy bieżącym utworze.

- Po końcu zwykłej kolejki aplikacja automatycznie odtwarza proponowane utwory.
  Działa zarówno po zakończeniu nagrania, jak i po naciśnięciu „następny”
  w aplikacji lub przez sterowanie systemowe. Spóźnione propozycje mogą
  zrealizować oczekujące przejście; pauza i zatrzymanie są respektowane.
  Zwykła kolejka i tryb powtarzania mają pierwszeństwo.

- Tło sięga krawędzi ekranu, a paski systemowe pozostają widoczne (przełącznik
  pełnego ekranu usunięto). Położenie kontrolek uwzględnia wycięcie aparatu
  i klawiaturę.
- Playlisty można od razu odtworzyć losowo: przycisk **Losowo** na stronie
  playlisty i ikona na jej karcie. **Odtwórz** zawsze gra w kolejności playlisty.
- Kolejkę zmienia się przeciąganiem: przytrzymaj utwór lub uchwyt ≡ i upuść go
  w nowym miejscu (karta Kolejka i lista pod pełnym odtwarzaczem). Propozycje też
  mają uchwyt: można zmienić ich kolejność albo przeciągnąć propozycję do kolejki
  (przy pustej kolejce na przerywane pole). Lista nie przebudowuje się w trakcie
  przeciągania.
- Pełny odtwarzacz: pod sterowaniem od razu lista „Następne w kolejce”, a pod nią
  propozycje „Dla Ciebie” (z przyciskiem odświeżania); obie listy obsługują
  przeciąganie. Osobny przycisk dodawania do playlisty obok tytułu.
- „Polecane dla Ciebie” na ekranie startowym opiera się na historii słuchania
  i playlistach, nie na bieżącym utworze. Lista nie przeładowuje się przy każdej
  partii odkryć ani po każdym zapisie historii; odświeża ją „Odkryj podobną muzykę”.
- Po „Zatrzymaj” przycisk „Następny” przełącza utwór bez wznawiania odtwarzania.
- Pojedynczy wynik wyszukiwania lub rekomendacja uruchamia tylko wybrany utwór;
  kolejne propozycje dobierane są do niego. Odtwarzanie playlist zachowuje ich kolejkę.
- Rekomendacje podczas słuchania opierają się na bieżącym wykonawcy, jawnych
  współpracach i powiązaniach we wspólnych playlistach. Popularność dawnych
  ulubionych nie wypiera bieżącego kontekstu. Wspólny ranking biblioteki i odkryć
  ogranicza powtórzenia oraz liczbę utworów jednego artysty. To dobór na podstawie
  metadanych, bez analizy podobieństwa samego dźwięku.
- Zmiana utworu odświeża odkrycia; wyniki docierają stopniowo, z odpowiedniego
  źródła YouTube/SoundCloud. Bieżący utwór, aktywna kolejka i alternatywne wrzutki
  znanych nagrań są wykluczane. Transmisje, krótkie klipy i długie kompilacje są
  filtrowane w propozycjach dla pojedynczego utworu.

- Odświeżony interfejs: dolna nawigacja z ikonami i aktywną zakładką, kompaktowy
  odtwarzacz, pełny ekran z okładką i sterowaniem, czytelniejsze karty playlist.
  Wyszukiwarka obsługuje przycisk szukania na klawiaturze i zachowuje wpisaną
  frazę podczas zmiany zakładki.
- Animowane przejścia ekranów, reakcje na dotyk, wejście/wyjście odtwarzacza,
  przenikanie okładek i płynny pasek postępu. Animacje respektują systemowe
  wyłączenie animatorów. W poziomie nagłówek jest kompaktowy.
- Wyszukiwanie YouTube Music / SoundCloud, odtwarzanie audio, przeglądanie kanału
  artysty i paginacja. Import playlist z linku, maksymalnie 10000 utworów.
- Playlisty: tworzenie, zmiana nazwy, okładki, dodawanie/usuwanie/przesuwanie
  utworów. Długie listy w interfejsie wyświetlane po 50 pozycji.
- Import lokalnego audio przez systemowy selektor, trwałe uprawnienia URI,
  migracja biblioteki z wersji Android 0.1 bez usuwania oryginalnego pliku.
- Kolejka: następny, na końcu, zmiana kolejności, usuwanie, shuffle/repeat.
  Osobna sekcja propozycji kontynuujących odtwarzanie po końcu playlisty.
  Zwarte wiersze z okładką, artystą i czasem; akcje w menu `⋮`, dotknięcie
  wiersza odtwarza utwór. Sekcja bieżącego utworu i licznik następnych.
  Długie kolejki ładowane po 50 wierszy. Menu odrzuca nieaktualny wybór,
  jeżeli kolejka zmieniła się podczas jego wyświetlania.
- Rekomendacje na podstawie playlist, kontekstu i historii. Ograniczone zapytania
  o artystów do źródła, lokalny ranking i cache odkryć. Historia nalicza faktyczne
  słuchanie, nie czas pauzy ani skoki po pasku czasu.
- MediaSessionService, sterowanie systemowe/Bluetooth, audio focus, reakcja na
  odłączenie słuchawek. Następny utwór przygotowywany w cache (limit cache 200 MB,
  przygotowanie do 80 MB, pomijane długie nagrania).
- Crossfade 1–15 sekund dla odpowiednio długich, przewijalnych utworów, kiedy
  następny jest gotowy; korektor basów i tonów wysokich przez efekty Androida.
- Język polski/angielski, wybór akcentu, odtworzenie ustawień wyglądu z kopii.
- Eksport/import JSON zgodny z PC, podgląd przed przywróceniem, kopia awaryjna,
  bezpieczne łączenie playlist i historii, atomowy zapis biblioteki.
- Integracja Google Drive: logowanie Google Identity, lista kopii, zapis i
  przywracanie wspólnego pliku, kontrola konfliktów osobno dla każdego konta,
  opcjonalna automatyczna kopia i historia. Konfiguracja wydawcy opisana w
  [GOOGLE_DRIVE_SETUP.md](GOOGLE_DRIVE_SETUP.md).

## Uruchomienie i budowanie

Android 8.0+ (API 26); APK zawiera arm64-v8a i x86_64. Telefon testowy: Nothing A063.
Potrzebne JDK 17 lub 21, Python 3.14, Android SDK Platform 35 i Build Tools 35.0.0.
Otwórz ten folder w Android Studio i użyj dołączonego Gradle Wrapper 8.11.1.
Ścieżkę SDK ustaw lokalnie w ignorowanym `local.properties`:

```properties
sdk.dir=/twoja/sciezka/Android/Sdk
```

```sh
./gradlew :app:assembleDebug :app:lintDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`. Nie publikuj klucza debug jako
klucza docelowego wydania. Zależności Python są przypięte w `app/build.gradle`;
aktualizacja yt-dlp wymaga nowej kompilacji APK.

## Weryfikacja

Z katalogu głównego repozytorium, z Pythonem mającym PyQt6 do testu zgodności PC:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s android/tests -v
```

Z tego folderu:

```sh
./gradlew :app:assembleDebugAndroidTest
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell am instrument -w -e class io.github.miniu123.musiccrow.DriveProtocolTest io.github.miniu123.musiccrow.test/androidx.test.runner.AndroidJUnitRunner
```

Osobne testy sieciowe: `OnlineSourcesTest` oraz `PlaybackSmokeTest` zamiast
`DriveProtocolTest`. Testy odtwarzania wymagają **odblokowanego telefonu** przy
starcie; Android 15 odmawia audio focus aplikacji uruchomionej spoza pierwszego
planu. Po uruchomieniu muzyki sprawdzana jest kontynuacja w tle. Materiał testowy
jest wyciszony albo zawiera ciszę. Testy nie zapisują kopii na koncie Google.

Potwierdzone 25.10.2026: testy kompatybilności z formatem PC i atomowego zapisu,
8 testów zabezpieczeń protokołu Drive na telefonie, wyszukiwanie i rozwiązywanie
URL YouTube/SoundCloud na telefonie, dekodowanie audio YouTube w tle oraz
przejście crossfade na lokalnym materiale testowym. Kompilacja i Android Lint
są uruchamiane po zmianach; raport: `app/build/reports/lint-results-debug.html`.

## Co nadal wymaga weryfikacji przed wydaniem

To wersja rozwojowa, nie deklaracja pełnej zgodności produkcyjnej z PC.
Rzeczywisty zapis i przywrócenie konta Google czekają na rejestrację klienta
OAuth Android w projekcie wersji PC i test użytkownika. Pełny katalog źródeł
online może zawierać prywatne, regionalnie ograniczone lub niedostępne nagrania.
Korektor zależy od implementacji telefonu; jakość odsłuchowa crossfade wymaga
sprawdzenia na muzyce i innych urządzeniach. Przy zmianie fokusu audio crossfade
jest kończony, żeby oba odtwarzacze respektowały pauzę.

Nie ma automatycznego wznowienia kolejki po zabiciu procesu/reboocie, zadania
kopii po zamknięciu procesu ani przeciągania kolejki palcem (są przyciski
przesuwania). Dostęp do lokalnych plików i ich audio nie przenosi się przez
kopię Drive. Pełny długotrwały test Bluetooth, połączeń telefonicznych, starszych
Androidów, bardzo dużych bibliotek i prawdziwej wymiany kopii PC↔Android pozostaje
w checklistcie wydania.

## Układ kodu

- `app/src/main/java/.../MainActivity.java`: ekrany i działania użytkownika.
- `CrowApp.java`: uruchomienie Pythona, dostęp do biblioteki, planowanie kopii.
- `PlaybackService.java`, `AudioSources.java`, `Track.java`: sesja audio,
  źródła/cache, historia i kolejka/rekomendacje.
- `DriveClient.java`, `DriveSync.java`: protokół Drive i autoryzacja Android.
- `app/src/main/python/crow.py`: biblioteka, kopie, walidacja i łączenie danych.
- `sources.py`: yt-dlp, wyszukiwanie i kanały.
- `recommendations.py`: niezależne od Qt funkcje rankingu z desktopu.

Dokumentacja architektury Media3:
https://developer.android.com/media/media3/session/background-playback
