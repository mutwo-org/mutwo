"""Render signing signals from mutwo data via `ISiS <https://forum.ircam.fr/projects/detail/isis/>`_.

ISiS (IRCAM Singing Synthesis) is a `"command line application for singing
synthesis that can be used to generate singing signals by means of synthesizing
them from melody and lyrics."
<https://isis-documentation.readthedocs.io/en/latest/Intro.html#the-isis-command-line>`_.
"""

import numbers
import os
import typing

from mutwo.events import basic

from mutwo import converters
from mutwo import parameters

__all__ = ("IsisScoreConverter", "IsisConverter")

ConvertableEvents = typing.Union[
    basic.SimpleEvent, basic.SequentialEvent[basic.SimpleEvent],
]
ExtractedData = typing.Tuple[
    # duration, consonants, vowel, pitch, volume
    parameters.abc.DurationType,
    typing.Tuple[str],
    str,
    parameters.abc.Pitch,
    parameters.abc.Volume,
]


class IsisScoreConverter(converters.abc.EventConverter):
    """Class to convert mutwo events to a `ISiS <https://forum.ircam.fr/projects/detail/isis/>`_ score file.

    :param path: where to write the ISiS score file
    :param simple_event_to_pitch: Function to extract an instance of
        :class:`mutwo.parameters.abc.Pitch` from a simple event.
    :param simple_event_to_volume:
    :param simple_event_to_vowel:
    :param simple_event_to_consonants:
    :param tempo: Tempo in beats per minute (BPM). Defaults to 60.
    :param global_transposition: global transposition in midi numbers. Defaults to 0.
    :param n_events_per_line: How many events the score shall contain per line.
        Defaults to 5.
    """

    def __init__(
        self,
        path: str,
        simple_event_to_pitch: typing.Callable[
            [basic.SimpleEvent], parameters.abc.Pitch
        ] = lambda simple_event: simple_event.pitch_or_pitches[0],
        simple_event_to_volume: typing.Callable[
            [basic.SimpleEvent], parameters.abc.Volume
        ] = lambda simple_event: simple_event.volume,
        simple_event_to_vowel: typing.Callable[
            [basic.SimpleEvent], str
        ] = lambda simple_event: simple_event.vowel,
        simple_event_to_consonants: typing.Callable[
            [basic.SimpleEvent], typing.Tuple[str]
        ] = lambda simple_event: simple_event.consonants,
        tempo: numbers.Number = 60,
        global_transposition: int = 0,
        default_sentence_loudness: typing.Union[numbers.Number, None] = None,
        n_events_per_line: int = 5,
    ):
        self.path = path
        self._tempo = tempo
        self._global_transposition = global_transposition
        self._default_sentence_loudness = default_sentence_loudness
        self._n_events_per_line = n_events_per_line

        self._extraction_functions = (
            simple_event_to_consonants,
            simple_event_to_vowel,
            simple_event_to_pitch,
            simple_event_to_volume,
        )

    # ###################################################################### #
    #                           private methods                              #
    # ###################################################################### #

    def _make_key_from_extracted_data_per_event(
        self,
        key_name: str,
        extracted_data_per_event: typing.Tuple[ExtractedData],
        key: typing.Callable[[ExtractedData], typing.Tuple[str]],
    ) -> str:
        objects_per_line = [[]]
        for nth_event, extracted_data in enumerate(extracted_data_per_event):
            objects_per_line[-1].extend(key(extracted_data))
            if nth_event % self._n_events_per_line == 0:
                objects_per_line.append([])

        join_string = ",\n{}".format(" " * (len(key_name) + 2))
        objects = join_string.join(
            [", ".join(line) for line in objects_per_line if line]
        )
        return "{}: {}".format(key_name, objects)

    def _make_lyrics_section_from_extracted_data_per_event(
        self, extracted_data_per_event: typing.Tuple[ExtractedData],
    ) -> str:
        xsampa = self._make_key_from_extracted_data_per_event(
            "xsampa",
            extracted_data_per_event,
            lambda extracted_data: extracted_data[1] + (extracted_data[2],),
        )

        lyric_section = "[lyrics]\n{}".format(xsampa)
        return lyric_section

    def _make_score_section_from_extracted_data_per_event(
        self, extracted_data_per_event: typing.Tuple[ExtractedData],
    ) -> str:
        midi_notes = self._make_key_from_extracted_data_per_event(
            "midiNotes",
            extracted_data_per_event,
            lambda extracted_data: (str(extracted_data[3].midi_pitch_number),),
        )
        rhythm = self._make_key_from_extracted_data_per_event(
            "rhythm",
            extracted_data_per_event,
            lambda extracted_data: (str(extracted_data[0]),),
        )
        loud_accents = self._make_key_from_extracted_data_per_event(
            "loud_accents",
            extracted_data_per_event,
            lambda extracted_data: (str(extracted_data[4].amplitude),),
        )
        score_section = (
            "[score]\n{}\nglobalTransposition: {}\n{}\n{}\ntempo: {}".format(
                midi_notes,
                self._global_transposition,
                rhythm,
                loud_accents,
                self._tempo,
            )
        )
        return score_section

    def _convert_simple_event(
        self,
        simple_event_to_convert: basic.SimpleEvent,
        absolute_entry_delay: parameters.abc.DurationType,
    ) -> typing.Tuple[ExtractedData]:
        duration = simple_event_to_convert.duration

        extracted_data = [duration]
        for extraction_function in self._extraction_functions:
            try:
                extracted_information = extraction_function(simple_event_to_convert)
            except AttributeError:
                return (
                    (
                        duration,
                        tuple([]),
                        "_",
                        parameters.pitches.WesternPitch("c", -1),
                        parameters.volumes.DirectVolume(0),
                    ),
                )

            extracted_data.append(extracted_information)

        return (tuple(extracted_data),)

    def _convert_simultaneous_event(
        self,
        simultaneous_event_to_convert: basic.SimultaneousEvent,
        absolute_entry_delay: parameters.abc.DurationType,
    ):
        message = (
            "Can't convert instance of SimultaneousEvent to ISiS Score. ISiS is only a"
            " monophonic synthesizer and can't read multiple simultaneous voices!"
        )
        raise NotImplementedError(message)

    # ###################################################################### #
    #                             public api                                 #
    # ###################################################################### #

    def convert(self, event_to_convert: ConvertableEvents) -> None:
        """Render ISiS score file from the passed event.

        :param event_to_convert: The event that shall be rendered to a ISiS score
            file.

        **Example:**

        >>> from mutwo.events import basic, music
        >>> from mutwo.parameters import pitches
        >>> from mutwo.converters.frontends import isis
        >>> notes = basic.SequentialEvent(
        >>>    [
        >>>         music.NoteLike(pitches.WesternPitch(pitch_name), 0.5, 0.5)
        >>>         for pitch_name in 'c f d g'.split(' ')
        >>>    ]
        >>> )
        >>> for consonants, vowel, note in zip([[], [], ['t'], []], ['a', 'o', 'e', 'a'], notes):
        >>>     note.vowel = vowel
        >>>     note.consonants = consonants
        >>> isis_score_converter = isis.IsisScoreConverter('my_singing_score')
        >>> isis_score_converter.convert(notes)
        """

        extracted_data_per_event = self._convert_event(event_to_convert, 0)
        lyrics_section = self._make_lyrics_section_from_extracted_data_per_event(
            extracted_data_per_event
        )
        score_section = self._make_score_section_from_extracted_data_per_event(
            extracted_data_per_event
        )
        with open(self.path, "w") as f:
            f.write("\n\n".join([lyrics_section, score_section]))


class IsisConverter(converters.abc.Converter):
    """Generate audio files with `ISiS <https://forum.ircam.fr/projects/detail/isis/>`_.

    :param path: where to write the sound file
    :param isis_score_converter: The :class:`IsisScoreConverter` that shall be used
        to render the ISiS score file from a mutwo event.
    :param *flag: Flag that shall be added when calling ISiS. Several of the supported
        ISiS flags can be found in :mod:`mutwo.converters.frontends.isis_constants`.
    :param remove_score_file: Set to True if :class:`IsisConverter` shall remove the
        ISiS score file after rendering. Defaults to False.

    **Disclaimer:** Before using the :class:`IsisConverter`, make sure ISiS has been
    correctly installed on your system.
    """

    def __init__(
        self,
        path: str,
        isis_score_converter: IsisScoreConverter,
        *flag: str,
        remove_score_file: bool = False
    ):
        self.flags = flag
        self.path = path
        self.isis_score_converter = isis_score_converter
        self.remove_score_file = remove_score_file

    def convert(self, event_to_convert: ConvertableEvents) -> None:
        """Render sound file via ISiS from mutwo event.

        :param event_to_convert: The event that shall be rendered.


        **Disclaimer:** Before using the :class:`IsisConverter`, make sure
        `ISiS <https://forum.ircam.fr/projects/detail/isis/>`_ has been
        correctly installed on your system.
        """

        self.isis_score_converter.convert(event_to_convert)
        command = "isis.sh -m {} -o {}".format(
            self.isis_score_converter.path, self.path
        )
        for flag in self.flags:
            command += " {} ".format(flag)

        os.system(command)

        if self.remove_score_file:
            os.remove(self.csound_score_converter.path)
