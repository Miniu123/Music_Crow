"""Live Polish/English UI translation; user content is never translated."""
import re
import weakref
from PyQt6.QtCore import QObject, pyqtSignal, QCoreApplication, QTranslator, QLibraryInfo

# Polish source strings are stable identifiers for the interface.
EN = {
    'Wróć do ulubionych': 'Rediscover a favourite',
    'Upuść utwór tutaj, aby odtworzyć go jako następny.': 'Drop a track here to play it next.',
    'DYSK GOOGLE': 'GOOGLE DRIVE',
    'Ustawienia, playlisty i okładki zapisujemy w jednym prywatnym pliku music-crow-config.json na Dysku zalogowanego użytkownika.': 'Settings, playlists and covers are stored in one private music-crow-config.json file on the signed-in user’s Google Drive.',
    'Na Dysku jest nieznana lub nowsza kopia. Przywróć ją przed kolejnym zapisem.': 'Drive contains an unknown or newer backup. Restore it before saving again.',
    'Zapisuj ustawienia, playlisty i okładki na swoim Dysku Google. Każde urządzenie ma osobną kopię.': 'Back up settings, playlists and covers to your Google Drive. Each device keeps a separate backup.',
    'Wybierz konfigurację Google…': 'Choose Google configuration…',
    'Pierwsze uruchomienie wymaga pliku OAuth aplikacji komputerowej. Instrukcja: README → Dysk Google.': 'First-time setup requires a desktop OAuth configuration file. See README → Google Drive.',
    'Automatycznie zapisuj kopię': 'Back up automatically',
    'Uwzględniaj historię słuchania': 'Include listening history',
    'Zaloguj przez Google': 'Sign in with Google',
    'Wyloguj': 'Sign out',
    'Zapisz kopię teraz': 'Back up now',
    'Przywróć kopię…': 'Restore backup…',
    'Ostatnia kopia:': 'Last backup:',
    'Dysk Google nie jest połączony.': 'Google Drive is not connected.',
    'Konfiguracja Google gotowa. Możesz się zalogować.': 'Google configuration is ready. You can sign in.',
    'Wybierz plik OAuth typu Aplikacja komputerowa z Google Cloud.': 'Choose a Desktop app OAuth file from Google Cloud.',
    'Brakuje bibliotek Google. Zainstaluj zależności projektu.': 'Google libraries are missing. Install the project dependencies.',
    'Najpierw wybierz plik konfiguracji Google.': 'Choose the Google configuration file first.',
    'Własna konfiguracja Google (zaawansowane)': 'Custom Google configuration (advanced)',
    'Autor aplikacji musi najpierw skonfigurować logowanie Google.': 'The app publisher must first configure Google sign-in.',
    'Konfiguracja logowania Google jest nieprawidłowa.': 'The Google sign-in configuration is invalid.',
    'Logowanie otworzy się w domyślnej przeglądarce systemowej.': 'Sign-in opens in your default system browser.',
    'Nie udało się usunąć lokalnej sesji Google.': 'Could not remove the local Google session.',
    'Operacja anulowana.': 'Operation cancelled.',
    'Nie udało się przygotować kopii. Sprawdź lokalne pliki i rozmiar okładek.': 'Could not prepare the backup. Check local files and cover sizes.',
    'Dokończ logowanie w przeglądarce…': 'Finish signing in in your browser…',
    'Łączę z Dyskiem Google…': 'Connecting to Google Drive…',
    'Zapisuję kopię na Dysku Google…': 'Saving backup to Google Drive…',
    'Pobieram listę kopii…': 'Loading backups…',
    'Pobieram kopię danych…': 'Downloading backup…',
    'Połączono z Dyskiem Google.': 'Connected to Google Drive.',
    'Kopia została zapisana na Dysku Google.': 'Backup saved to Google Drive.',
    'Wybierz kopię do przywrócenia.': 'Choose a backup to restore.',
    'Brak kopii na tym koncie Google.': 'No backups on this Google account.',
    'Kopia gotowa do przywrócenia.': 'Backup is ready to restore.',
    'Nie udało się zapisać lokalnych danych Google.': 'Could not save local Google data.',
    'Przywrócono dane. Poprzedni stan zapisano w folderze recovery.': 'Data restored. The previous state was saved in the recovery folder.',
    'Przywracanie nie powiodło się. Sprawdź kopię danych i dostęp do plików.': 'Restore failed. Check the backup and file permissions.',
    'Przywrócić ustawienia i playlisty? Różne playlisty o tej samej nazwie zachowamy osobno. Obecne dane zapiszemy najpierw w lokalnej kopii.': 'Restore settings and playlists? Different playlists with the same name will be kept separately. Current data will first be saved in a local recovery copy.',
    'Playlisty:': 'Playlists:',
    'Utwory:': 'Tracks:',
    'Logowanie anulowane lub przekroczono czas oczekiwania.': 'Sign-in cancelled or timed out.',
    'Nieprawidłowa kopia danych.': 'Invalid backup.',
    'Kopia przekracza limit 40 MB.': 'Backup exceeds the 40 MB limit.',
    'Zbyt wiele kopii na Dysku Google.': 'Too many backups on Google Drive.',
    'Brak dostępu do Dysku. Sprawdź, czy Drive API jest włączone w projekcie Google.': 'Drive access denied. Check that Drive API is enabled in the Google project.',
    'Operacja Google nie powiodła się. Sprawdź połączenie lub zaloguj się ponownie.': 'Google operation failed. Check your connection or sign in again.',

    'Przejdź do artysty / kanału': 'Go to artist / channel',
    '← Wróć': '← Back', 'Pokaż więcej': 'Show more', 'Spróbuj ponownie': 'Try again',
    'Utwory z kanału wykonawcy': "Tracks from the artist's channel",
    'Wczytuję utwory artysty…': 'Loading artist tracks…',
    'Nie znaleziono adresu kanału. Wyniki wyszukiwania nazwy artysty.': 'Channel address unavailable. Showing search results for the artist name.',
    'Brak dostępnych utworów na tym kanale.': 'No available tracks on this channel.',
    'Brak informacji o artyście lub kanale tego utworu.': 'No artist or channel information for this track.',
    'Nie udało się wczytać kanału. Sprawdź połączenie i spróbuj ponownie.': 'Could not load the channel. Check your connection and try again.',

    'Czy usunąć playlistę „{name}”?\n\nTej operacji nie można cofnąć.': 'Delete playlist “{name}”?\n\nThis cannot be undone.',
    'Ustawienia': 'Settings', 'JĘZYK': 'LANGUAGE', 'Język aplikacji': 'Application language',
    'Zmiana języka działa od razu.': 'Language changes take effect immediately.',
    'Dopasuj wygląd i brzmienie do siebie.': 'Make the look and sound your own.', 'Gotowe': 'Done',
    'MOTYW KOLORYSTYCZNY': 'COLOUR THEME', 'KOLORY APLIKACJI': 'APP COLOURS',
    'ODTWARZANIE I BRZMIENIE': 'PLAYBACK & SOUND', 'Kolor akcentu': 'Accent colour',
    'Przyciski, aktywne elementy i suwaki': 'Buttons, active controls and sliders',
    'Pasek odtwarzania': 'Player bar', 'Tło dolnego panelu odtwarzacza': 'Background of the bottom player bar',
    'Tło okna': 'Window background', 'Podstawowy kolor aplikacji': 'Base application colour',
    'Gradient · góra': 'Gradient · top', 'Górna część głównego panelu': 'Top of the main panel',
    'Gradient · dół': 'Gradient · bottom', 'Dolna część głównego panelu': 'Bottom of the main panel',
    'Zmień kolor': 'Change colour', 'Wybierz kolor': 'Choose colour',
    'Przygotuj następny utwór': 'Prepare the next track',
    'Pobieraj kolejny utwór w tle, aby skrócić przerwę w odtwarzaniu.': 'Download the next track in the background to reduce playback gaps.',
    'Płynne przejścia': 'Crossfade', 'Mieszaj końcówkę utworu z początkiem następnego.': 'Blend the end of a track into the next one.',
    'Długość przejścia': 'Crossfade duration', 'Czas nakładania utworów w sekundach.': 'Track overlap in seconds.',
    'Niskie tony': 'Bass', 'Wzmocnienie basu w dB.': 'Bass gain in dB.',
    'Wysokie tony': 'Treble', 'Wzmocnienie wysokich częstotliwości w dB.': 'Treble gain in dB.',
    '  Strona główna': '  Home', '  Szukaj': '  Search', '  Ustawienia': '  Settings',
    'TWOJA MUZYKA': 'YOUR MUSIC', 'BIBLIOTEKA': 'LIBRARY', 'Twoja muzyka': 'Your music',
    'MUSIC CROW  /  Twoja przestrzeń muzyki': 'MUSIC CROW  /  Your music space',
    'Dzień dobry': 'Good morning', 'Miłego popołudnia': 'Good afternoon', 'Dobry wieczór': 'Good evening',
    'Twoja muzyka. Twoje tempo. Włącz coś dla siebie.': 'Your music. Your pace. Play something you love.',
    'Odkryj swoje\nnowe brzmienie.': 'Find your next\nfavourite sound.',
    'YouTube Music i SoundCloud w jednym miejscu. Twoja biblioteka, Twój wybór.': 'YouTube Music and SoundCloud in one place. Your library, your choice.',
    'Odkrywaj muzykę →': 'Explore music →', 'Twoje playlisty': 'Your playlists',
    'Zbierz ulubione utwory w jednym miejscu. Utwórz pierwszą playlistę.': 'Bring your favourites together. Create your first playlist.',
    'Szukaj utworów lub wykonawców…': 'Search for songs or artists…',
    'Proponowane dla Ciebie': 'Recommended for you', 'Odśwież ↻': 'Refresh ↻', 'Przygotowuję propozycje…': 'Preparing recommendations…',
    'Utwórz playlistę': 'Create playlist', 'Nadaj nazwę swojej kolekcji i wybierz okładkę.': 'Name your collection and choose a cover.',
    'Nazwa playlisty…': 'Playlist name…', 'Wybierz okładkę (opcjonalnie)': 'Choose cover (optional)',
    'Importuj playlistę': 'Import playlist', 'Wklej link do playlisty z YouTube lub SoundCloud.': 'Paste a YouTube or SoundCloud playlist link.',
    'Odkrywaj muzykę': 'Discover music', 'Czego chcesz posłuchać?': 'What would you like to listen to?',
    'Wpisz tytuł lub wykonawcę i odkryj kolejne utwory.': 'Enter a song or artist to discover more music.',
    'Szukam utworów…': 'Searching for tracks…', 'Brak wyników. Spróbuj innego tytułu lub wykonawcy.': 'No results. Try another title or artist.',
    'Odtwórz wszystko': 'Play all', 'Losowo': 'Shuffle', 'Usuń': 'Delete',
    'Kolejki odtwarzania': 'Playback queues', 'Losuj playlistę': 'Shuffle playlist',
    'Z playlisty': 'From playlist', 'Twoja kolejność odtwarzania': 'Your playback order',
    'Proponowane': 'Suggested', 'Odtworzą się automatycznie po playliście': 'Play automatically after the playlist',
    'Teraz odtwarzane': 'Now playing', 'Następny →': 'Play next →',
    'Przenieś do kolejki z playlisty i odtwórz po bieżącym utworze': 'Move to the playlist queue and play after the current track',
    'Odtworzy się po playliście. Możesz przeciągnąć go do lewej kolejki lub wybrać Następny.': 'Plays after the playlist. Drag it to the left queue or choose Play next.',
    'Upuść propozycję tutaj, aby odtworzyć ją jako następną.': 'Drop a suggestion here to play it next.',
    'Po tej kolejce odtworzą się proponowane utwory.': 'Suggested tracks will play after this queue.',
    'Tutaj pojawią się propozycje do dalszego słuchania.': 'Suggestions for continued listening will appear here.',
    'Wybierz utwór lub playlistę, aby otrzymać propozycje.': 'Choose a track or playlist to get suggestions.',
    'Wybierz utwór': 'Choose a track', 'Pokaż dwie kolejki': 'Show both queues',
    'Odtwarzaj losowo': 'Shuffle playback', 'Poprzedni utwór': 'Previous track', 'Odtwórz / pauza': 'Play / pause',
    'Następny utwór': 'Next track', 'Powtarzanie': 'Repeat', 'Wycisz / przywróć głośność': 'Mute / restore volume',
    'Zapisz na playliście': 'Save to playlist', 'Powtarzanie wyłączone': 'Repeat off', 'Powtarzaj playlistę': 'Repeat playlist', 'Powtarzaj utwór': 'Repeat track',
    'Pobieram następny utwór…': 'Downloading the next track…', 'Następny utwór gotowy': 'Next track ready',
    'Następny utwór odtworzy się online': 'Next track will stream online', 'Odtwarzanie 🎵': 'Playing 🎵',
    'Usuń z kolejki': 'Remove from queue',
    'TWÓJ MUZYCZNY ŚWIAT': 'YOUR MUSIC WORLD', 'Uruchamianie odtwarzacza...': 'Starting the player...', 'Uruchamianie...': 'Starting…',
    'Nie udało się uruchomić aplikacji. Szczegóły znajdziesz w terminalu.': 'The application could not start. Check the terminal for details.',
    'Dopasowane do Twojej historii i playlist.': 'Based on your listening history and playlists.',
    'Posłuchaj muzyki lub dodaj utwory do playlist, aby otrzymać propozycje.': 'Listen to music or add tracks to playlists to get recommendations.',
    'Szukam muzyki dopasowanej do Ciebie…': 'Finding music for you…',
    'Nie udało się pobrać wszystkich nowości. Możesz spróbować ponownie.': 'Some new tracks could not be fetched. You can try again.',
    'Dopasowane do odtwarzania. Wybierz Następny lub zostaw do odtworzenia po playliście.': 'Based on your playback. Choose Play next or leave tracks to play after the playlist.',
    'Wybierz utwór lub playlistę, aby otrzymać propozycje do dalszego słuchania.': 'Choose a track or playlist for listening suggestions.',
    'Z Twoich playlist': 'From your playlists', 'Z Twojej historii': 'From your history', 'Z Twojej biblioteki': 'From your library',
    'Dodaj do playlisty': 'Add to playlist', 'Utwórz nową playlistę…': 'Create a new playlist…',
    'Nie udało się zapisać utworu.': 'Could not save the track.', 'Playlista o tej nazwie już istnieje.': 'A playlist with this name already exists.',
    'Podaj nazwę playlisty.': 'Enter a playlist name.', 'Zapisano na playliście': 'Saved to playlist',
}
# Older screens still use these English labels as their source text.
LEGACY = {
    'Save to playlist': 'Zapisz na playliście', '▶️ Play Next': 'Odtwórz jako następny', '➕ Add to Queue': 'Dodaj do kolejki',
    'Import playlist from URL': 'Importuj playlistę z linku', 'New Playlist': 'Nowa playlista', 'New playlist': 'Nowa playlista',
    'New name:': 'Nowa nazwa:', 'Playlist name:': 'Nazwa playlisty:', 'Rename Playlist': 'Zmień nazwę playlisty',
    'Rename playlist': 'Zmień nazwę playlisty', '✏️  Rename': 'Zmień nazwę',
    'No tracks found in this playlist.': 'Nie znaleziono utworów na tej playliście.',
    'Please enter a playlist URL': 'Wklej link do playlisty', '⏳ Importing...': 'Importuję…',
    'Click to set cover image': 'Kliknij, aby wybrać okładkę', 'Select Cover Image': 'Wybierz okładkę',
    'Delete Playlist': 'Usuń playlistę', '🖼️ Image Selected': 'Wybrano okładkę',
    'Images (*.png *.jpg *.jpeg)': 'Obrazy (*.png *.jpg *.jpeg)',
    'Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)': 'Obrazy (*.png *.jpg *.jpeg *.webp *.bmp);;Wszystkie pliki (*)',
}
EN.update({
    'Odtwórz jako następny': 'Play next', 'Dodaj do kolejki': 'Add to queue', 'Importuj playlistę z linku': 'Import playlist from URL',
    'Nowa playlista': 'New playlist', 'Nowa nazwa:': 'New name:', 'Nazwa playlisty:': 'Playlist name:',
    'Zmień nazwę playlisty': 'Rename playlist', 'Zmień nazwę': 'Rename',
    'Nie znaleziono utworów na tej playliście.': 'No tracks found in this playlist.', 'Wklej link do playlisty': 'Enter a playlist URL',
    'Importuję…': 'Importing…', 'Kliknij, aby wybrać okładkę': 'Click to set cover image',
    'Wybierz okładkę': 'Choose cover image', 'Usuń playlistę': 'Delete playlist', 'Wybrano okładkę': 'Cover selected',
    'Obrazy (*.png *.jpg *.jpeg)': 'Images (*.png *.jpg *.jpeg)',
    'Obrazy (*.png *.jpg *.jpeg *.webp *.bmp);;Wszystkie pliki (*)': 'Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)',
})
EN.update({
    'Inicjalizacja silnika MPV i kodeków...': 'Initialising MPV and codecs…',
    'Wczytywanie playlist i biblioteki utworów...': 'Loading playlists and the music library…',
    'Ładowanie motywów i korektora graficznego...': 'Loading themes and the equaliser…',
    'Przygotowywanie interfejsu użytkownika...': 'Preparing the interface…',
    'Wszystko gotowe! Uruchamianie...': 'All ready! Starting…',
    'Import timed out (playlist may be too large)': 'Import timed out (the playlist may be too large)',
})
PATTERNS = [
    (r'Playlisty: (\d+)', 'Playlists: {}'), (r'Utwory: (\d+)', 'Tracks: {}'), (r'Wyniki: (\d+)', 'Results: {}'),
    (r'Na podstawie: (.*)', 'Based on: {}'),
    (r'Pasuje do teraz: (.*)', 'Matches what is playing: {}'),
    (r'Powiązane przez playlisty: (.*)', 'Connected through your playlists: {}'),
    (r'Importing\.\.\. (\d+)/(\d+) tracks', 'Importing… {}/{} tracks'),
    (r'✅ Imported (\d+) tracks!', 'Imported {} tracks!'), (r'Error: (.*)', 'Error: {}'),
]


class LanguageManager(QObject):
    changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.language = 'pl'
        self._settings = None
        self._bindings = weakref.WeakKeyDictionary()
        self._qt_translator = None

    def configure(self, settings):
        self._settings = settings
        language = settings.current_theme.get('LANGUAGE', 'pl') if settings else 'pl'
        self.set_language(language if language in ('pl', 'en') else 'pl', persist=False)
        if self.language == 'pl' and self._qt_translator is None:
            self._load_qt_translation()

    def set_language(self, language, persist=True):
        if language not in ('pl', 'en'):
            raise ValueError('Unsupported language')
        if persist and self._settings:
            self._settings.current_theme['LANGUAGE'] = language
            self._settings.save_theme()
        if language == self.language:
            return
        self.language = language
        self._load_qt_translation()
        for widget, fields in list(self._bindings.items()):
            for field, source in fields.items():
                try:
                    getattr(widget, 'set' + field[0].upper() + field[1:])(self.translate(source))
                except RuntimeError:
                    break
        self.changed.emit(language)

    def _load_qt_translation(self):
        app = QCoreApplication.instance()
        if app is None:
            return
        if self._qt_translator is not None:
            app.removeTranslator(self._qt_translator)
            self._qt_translator.deleteLater()
            self._qt_translator = None
        if self.language == 'pl':
            translator = QTranslator(self)
            directory = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if translator.load('qtbase_pl', directory):
                app.installTranslator(translator)
                self._qt_translator = translator
            else:
                translator.deleteLater()

    def translate(self, source):
        source = str(source)
        canonical = LEGACY.get(source, source)
        if self.language == 'pl':
            if source.startswith('Error: '):
                return 'Błąd: ' + self.translate(source[7:])
            progress = re.fullmatch(r'Importing\.\.\. (\d+)/(\d+) tracks', source)
            if progress:
                return 'Importuję… {}/{} utworów'.format(*progress.groups())
            imported = re.fullmatch(r'✅ Imported (\d+) tracks!', source)
            if imported:
                return 'Zaimportowano {} utworów!'.format(*imported.groups())
            return canonical
        if canonical in EN:
            return EN[canonical]
        for pattern, template in PATTERNS:
            match = re.fullmatch(pattern, canonical, flags=re.DOTALL)
            if match:
                return template.format(*match.groups())
        return source

    def unbind(self, widget):
        self._bindings.pop(widget, None)

    def bind(self, widget, source, field='text'):
        self._bindings.setdefault(widget, {})[field] = str(source)
        getattr(widget, 'set' + field[0].upper() + field[1:])(self.translate(source))
        return widget


language_manager = LanguageManager()


def tr(source):
    return language_manager.translate(source)


def text(widget, source):
    return language_manager.bind(widget, source)


def set_text(widget, source, field='text'):
    return language_manager.bind(widget, source, field)
