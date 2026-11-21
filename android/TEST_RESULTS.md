# Testy Androida

## Logo autora 0.9.1 — 21 listopada 2026

- Ustawienia → „O aplikacji”: logo autora (Miniowski_), wersja i prawa autorskie;
  okno „Licencje i informacje” pokazuje bieżącą wersję zamiast starego „0.5.0-dev”.
- `assembleDebug`, `assembleDebugAndroidTest`: sukces. Testy lokalne: 39 / 39.
- Testy na urządzeniu nie zostały uruchomione — telefon był odłączony.
  `settingsHaveNoFullscreenSwitchAndBarsStayVisible` sprawdza teraz także logo.

## Odtwarzacz, kolejka i propozycje 0.9.0 — 21 listopada 2026

- Pełny odtwarzacz: pod sterowaniem lista „Następne w kolejce”, pod nią propozycje
  „Dla Ciebie”; osobny okrągły przycisk dodawania do playlisty obok tytułu.
- Przeciąganie w kolejce i w propozycjach (strefy upuszczania na całej liście,
  bez przebudowy w trakcie przeciągania); propozycję można przeciągnąć do kolejki.
- Przycisk „Losowo” i ikona odtwarzania losowego na kartach playlist; „Odtwórz”
  gra w kolejności playlisty.
- Ekran startowy: propozycje z historii i playlist, bez przeładowania przy każdej
  partii odkryć i po każdym zapisie historii. Usunięto przełącznik pełnego ekranu.
- Po „Zatrzymaj” przycisk „Następny” nie wznawia odtwarzania.
- Testy lokalne: 39 / 39. Nothing A063 (Android 15), testy na urządzeniu:
  `draggingAQueueTrackMovesIt`, `expandedPlayerShowsSuggestionsBelowTheQueue`,
  `settingsHaveNoFullscreenSwitchAndBarsStayVisible`,
  `navigationAndExpandedPlayerStayUsable`, `stoppedSkipStaysStopped`,
  `pausedSkipStaysPausedAndRepeatOneDoesNotAutoplay` — sukces.
- APK 0.9.0 (podpis debug, arm64-v8a i x86_64) zainstalowano na Nothing A063;
  uruchomienie bez awarii. SHA-256 w `releases/SHA256SUMS`.

## Import YouTube Music 0.8.0-dev — 1 listopada 2026

- Dodano przycisk w zakładce Playlisty, formularz linku, stan pobierania
  i podgląd nazwy oraz liczby utworów przed zapisem. Domyślna nazwa pochodzi
  ze źródła; kolizja proponuje kolejną nazwę. Zapis atomowo odrzuca kolizję
  zamiast łączyć import z istniejącą playlistą.
- Linki YouTube Music z `list`, także `watch?v=...&list=...`, są zamieniane
  na adres całej playlisty. Pozycja wideo i parametry udostępniania nie ograniczają
  importu. Puste playlisty nie stają się pojedynczym utworem. Niedostępne pozycje
  zwrócone przez źródło są pomijane i zliczane; limit pozostaje 10000 utworów.
- Testy lokalne: 38 / 38. Sprawdzono normalizację linków, kolejność, limit,
  puste i niedostępne listy, odrzucanie linków bez playlisty oraz ochronę zapisu
  istniejącej playlisty i zachowanie importu po ponownym uruchomieniu magazynu.
- `assembleDebug`, `assembleDebugAndroidTest`, `lintDebug`: sukces.
  Lint: 0 błędów, 13 ostrzeżeń.
- Nothing A063: rzeczywisty import muzycznej playlisty YouTube Music dłuższej
  niż 30 pozycji przeszedł. Test nie zapisywał tej playlisty w bibliotece użytkownika.
- Test interfejsu i zapisu: 1 / 1 (2,132 s). Przycisk jest dostępny w Playlistach,
  pusty link nie uruchamia importu, zapis zachowuje kolejność i odrzuca istniejącą
  nazwę. Tymczasowa playlista testowa została usunięta. Pierwsza próba testu klikała
  przed obsługą `OnShowListener`; po dodaniu oczekiwania na dialog test przeszedł.
- APK 0.8 zainstalowano na Nothing A063; SHA-256:
  `51396cd16c33a786e70260d0406921d301be54b8b41e848aa679556deabb8818`.

## Stabilniejsze propozycje i przygotowanie audio 0.7.0-dev — 31 października 2026

- Ranking domyślnie odrzuca remiksy, remiksy opisane po polsku, bootlegi,
  mashupy, nightcore oraz zmiany tempa. Kontekst wybranego remiksu dopuszcza
  podobne wersje. Samo pojawienie się nazwy wykonawcy w tytule innego artysty
  nie wystarcza do dopasowania; jawne oznaczenia `feat.` pozostają obsługiwane.
- Cache trafia do pierwszego rankingu i jest aktualizowany po każdej partii.
  Ponowne wejście do aplikacji nie przerywa trwającego zapytania tego samego
  utworu. Spóźnione partie ponownie sprawdzają aktualną kolejkę i wykluczenia.
- Przy braku następnego utworu w kolejce przygotowywana jest pierwsza propozycja.
  Zwykła kolejka, usunięcie propozycji, zatrzymanie oraz wyłączenie przygotowania
  są respektowane. Informacje o szukaniu, przygotowaniu i błędzie są widoczne
  w kolejce. Pauza działa podczas buforowania; replay dotyczy bieżącego utworu.
- Testy lokalne: 33 / 33. `assembleDebug`, `assembleDebugAndroidTest`,
  `lintDebug`: sukces; 0 błędów lint, 13 ostrzeżeń.
- Na Nothing A063 potwierdzono łącznie 12 różnych przypadków: kontynuację,
  crossfade, wybór utworu do przygotowania, pierwszeństwo zwykłej kolejki,
  wykluczenie usuniętej propozycji z późniejszej partii, przełącznik przygotowania,
  zachowanie cache i pojedynczego zapytania przy powrocie do aplikacji, pauzę
  podczas buforowania, replay oraz dotychczasowe testy interfejsu.
- Rzeczywiste zapytanie YouTube zwróciło pasujące propozycje oryginalnych nagrań.
  Oddzielny test potwierdził pobranie audio propozycji do cache przed jej startem,
  bez dodania jej do zwykłej kolejki (`getCachedBytes > 0`, `readyId` zgodne z URL).
- Pierwszy przebieg: 9 udanych przypadków i 2 błędy testów. Poprawiono metadane
  18-sekundowej próbki, którą prawidłowo odrzucał filtr krótkich nagrań, oraz
  oczekiwanie na możliwość przewijania po buforowaniu. Powtórzenie obu przypadków
  wraz z testem rzeczywistego cache: 3 / 3 (9,507 s).
- APK 0.7 zainstalowano na Nothing A063; SHA-256:
  `7098633f98124483d761b679d8cb539209ec38920e8d61486ea3ff2d52597685`.

## Automatyczna kontynuacja 0.6.0-dev — 26 października 2026

- Przycisk „następny” przechodzi do propozycji po wyczerpaniu zwykłej kolejki.
  Oba polecenia MediaController (`seekToNext`, `seekToNextMediaItem`) korzystają
  z tej samej obsługi, również dla sterowania systemowego.
- Koniec utworu uruchamia gotową propozycję lub czeka na późniejszy wynik.
  Zwykła kolejka ma pierwszeństwo; pauza, zatrzymanie i powtarzanie są respektowane.
  Przed dołączeniem propozycji ponownie odrzucane są zużyte i obecne w kolejce URL.
- `assembleDebug`, `assembleDebugAndroidTest`, `lintDebug`: sukces.
  Lint: 0 błędów, 13 ostrzeżeń. APK 0.6 zainstalowano na Nothing A063.
- Testy odtwarzania: 5 / 5 na odblokowanym Nothing A063 (14,103 s),
  z lokalnym bezgłośnym materiałem. Sprawdzono pierwszeństwo kolejki,
  oba polecenia następnego utworu, odrzucanie powtórzeń, koniec nagrania,
  gotowe i opóźnione propozycje, zatrzymanie oczekującego przejścia,
  skip podczas pauzy, powtarzanie jednego utworu oraz regresję crossfade.
  Pierwsza próba na zablokowanym i wygaszonym telefonie nie mogła wystartować
  audio (`playWhenReady=false`, bez błędu dekodera); powtórzenie przeszło.
  Polecenia systemowe sprawdzono przez MediaController, bez fizycznych słuchawek.
- `InterfaceTest`: 2 / 2 (5,655 s), weryfikacja kolejki, nawigacji,
  metadanych rozwiniętego odtwarzacza i przełącznika pełnego ekranu.
- SHA-256 APK: `94787e54038039d64f182607f0cc91bfd78f6c1943ef1830b1541b9312ab237d`.

## Propozycje i pełny ekran 0.5.0-dev — 26 października 2026

- Wybór pojedynczego wyniku wyszukiwania lub propozycji uruchamia jeden utwór;
  wybór utworu z playlisty zachowuje całą kolejkę playlisty.
- Ranking wspólnie ocenia bibliotekę i odkrycia w kontekście bieżącego utworu,
  ogranicza dominację historii oraz liczbę utworów jednego wykonawcy. Wyklucza
  bieżący utwór, kolejkę, alternatywne wrzutki, transmisje i kompilacje.
  Dobór korzysta z metadanych, bez analizy podobieństwa dźwięku.
- Pełny ekran obejmuje górę i dół aplikacji oraz rozwinięty odtwarzacz.
  Kontrolki uwzględniają wycięcie aparatu i klawiaturę; paski systemowe można
  wywołać gestem. Przełącznik znajduje się w ustawieniach wyglądu.
- Testy lokalne: 28 / 28, w tym 10 nowych przypadków rankingu rekomendacji.
- `assembleDebug`, `assembleDebugAndroidTest`, `lintDebug`: sukces.
  Lint: 0 błędów, 13 ostrzeżeń.
- `PlaybackSmokeTest#searchSelectionPlaysOneSongWhilePlaylistKeepsItsQueue`:
  1 / 1 na Nothing A063, z lokalnym bezgłośnym materiałem testowym.
- Końcowy `InterfaceTest`: 2 / 2 na Nothing A063 (6,336 s). Sprawdzono
  przełączanie widoczności paska statusu i nawigacji, pięć zakładek, kolejkę
  oraz rozwinięty odtwarzacz. Zrzuty kolejki i odtwarzacza sprawdzono wizualnie.
- APK 0.5 zainstalowany na telefonie. Po testach pozostawiono pełny ekran
  włączony zgodnie z prośbą użytkownika; potwierdzono zapis preferencji.
- SHA-256 APK: `a646419d61cd8062091b11c19102e6b3a33253412a0f750c0e25570ba8420696`.

## Kolejka i wygląd 0.4.0-dev — 26 października 2026

- Kolejka ma zwarte wiersze z okładką, artystą, czasem i menu opcji zamiast
  dużych kart z czterema przyciskami. Sekcje bieżącego utworu, następnych
  i rekomendacji; paginacja po 50 pozycji.
- Mniejszy nagłówek aplikacji, lżejsze listy utworów, neutralne powierzchnie
  i zaznaczenie nawigacji dopasowane do wybranego akcentu.
- `assembleDebug`, `assembleDebugAndroidTest`, `lintDebug`: sukces.
- Instalacja na Nothing A063: `adb install -r` — `Success`.
- `InterfaceTest`: 1 / 1 (4,9 s), z wypełnioną kolejką danych testowych.
  Sprawdzono pięć zakładek, odtwarzacz, przesunięcie utworu na następne miejsce,
  usuwanie i zachowanie bieżącego utworu. Nieaktualne menu nie usuwa utworu
  pod zmienionym indeksem. Podgląd kolejki z długim tytułem sprawdzony wizualnie.

## Interfejs 0.3.0-dev — 26 października 2026

- Nowa nawigacja z ikonami, karty playlist, kompaktowy i pełny odtwarzacz,
  wyszukiwanie z klawiatury, zapamiętywanie frazy przy zmianie zakładki.
- Animacje wejścia ekranów, reakcji na dotyk, okna odtwarzacza, zmiany okładki
  i postępu. Uwzględniają `ValueAnimator.areAnimatorsEnabled()`.
- `assembleDebug`, `assembleDebugAndroidTest`, `lintDebug`: sukces.
  Lint: 0 błędów, 13 ostrzeżeń.
- `InterfaceTest`: 1 / 1 na Nothing A063 także po końcowym dodaniu animacji
  (ponowny test 26 października, 4,733 s).
  Sprawdzone pięć zakładek, zaznaczenie nawigacji, dostępne miejsce na treść,
  aktualizacja metadanych pełnego odtwarzacza oraz sterowanie shuffle/repeat.
  Zrzuty wszystkich ekranów obejrzano podczas przeglądu wyglądu.
- Końcowy APK 0.3 z animacjami zainstalowano na Nothing A063 po ponownym
  podłączeniu telefonu: `adb install -r` zakończyło się `Success`.
  Zrzuty końcowego ekranu głównego i pełnego odtwarzacza sprawdzono wizualnie.
  Test potwierdza działanie interfejsu i zakończenie przejść ekranów; nie mierzy
  płynności animacji w klatkach na sekundę.

## Wyniki bazowej wersji — 25 października 2026

### Kompilacja APK 0.2

- JDK 21, SDK 35, Gradle Wrapper 8.11.1.
- `assembleDebug`, `assembleDebugAndroidTest`, `lintDebug`: sukces.
- Android Lint: 0 błędów. Pozostałe ostrzeżenia dotyczą głównie nowszych wersji
  zależności i tekstów interfejsu zapisanych w kodzie.
- Plik: `app/build/outputs/apk/debug/app-debug.apk` (~51 MB).
- APK 0.2 po poprawkach interfejsu zainstalowano na Nothing A063
  25 października 2026; `adb install -r` zakończyło się `Success`.
  Testy urządzenia opisane poniżej wykonano przed ostatnimi poprawkami wyglądu.

## Testy lokalne — 18 / 18

Polecenie z katalogu repozytorium:
`QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s android/tests -v`

Zakres: zgodność eksportu z desktopowym walidatorem; import formatu desktopu;
kolizje nazw i powtórne przywrócenie; łączenie historii bez podwójnego naliczania;
zgoda na historię w eksporcie; odrzucenie uszkodzonych i zbyt dużych danych;
przerwany zapis i kopia awaryjna; migracja wersji 0.1; kolejność playlist;
wykluczenia i różnorodność rekomendacji; dozwolone źródła, kanały i fallback
wyszukiwania artysty; brak cichego obcinania zbyt dużej playlisty.

## Testy na Nothing A063 / Android 15 — 12 / 12

- `DriveProtocolTest`: 8 / 8. Z izolowanymi preferencjami i atrapą transportu,
  bez dostępu do prawdziwego konta Google: nowa instalacja, inne konto, nowsza
  kopia i duplikaty blokują zapis; potwierdzona identyczna kopia nie jest wysyłana;
  pusty folder tworzy wspólny plik; stara kopia nie odblokowuje zapisu wspólnego
  pliku; limit rozmiaru jest egzekwowany.
- `OnlineSourcesTest`: 2 / 2. Rzeczywiste wyszukiwanie oraz odczyt adresu audio
  YouTube i SoundCloud.
- `PlaybackSmokeTest`: 2 / 2 po odblokowaniu telefonu. Faktyczne dekodowanie
  internetowego audio YouTube, kontynuacja po zamknięciu aktywności, przejście
  crossfade na lokalnym bezgłośnym materiale. Początkowe próby na zablokowanym
  telefonie nie przeszły: audio focus był niedostępny przy starcie spoza pierwszego
  planu. Test powtórzony na odblokowanym telefonie zakończył się powodzeniem.

## Jeszcze niepotwierdzone

Klient OAuth Android został utworzony i potwierdzony w konsoli Google w tym samym
projekcie co desktop. Prawdziwe logowanie Google, pobranie kopii PC, zapis
z telefonu i odczyt z PC nadal wymagają testu z kontem użytkownika.
Nie uznajemy testów protokołu za test prawdziwego konta. Instrukcja:
[GOOGLE_DRIVE_SETUP.md](GOOGLE_DRIVE_SETUP.md).

Nie wykonano długotrwałych odsłuchów crossfade, pełnej macierzy urządzeń,
Bluetooth/połączeń telefonicznych ani testu produkcyjnego wydania podpisanego
kluczem release.
