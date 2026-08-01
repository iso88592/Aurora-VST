#include "PluginProcessor.h"
#include "PluginEditor.h"

AruraMelodyProcessor::AruraMelodyProcessor()
    : AudioProcessor(BusesProperties().withOutput("Output", juce::AudioChannelSet::stereo(), true)),
      state(*this, nullptr, "AruraMelody", makeParameters()) {}

juce::AudioProcessorValueTreeState::ParameterLayout AruraMelodyProcessor::makeParameters()
{
    using P = juce::AudioParameterFloat;
    using R = juce::NormalisableRange<float>;
    juce::AudioProcessorValueTreeState::ParameterLayout result;
    result.add(std::make_unique<P>("creativity", "Creativity", R(0, 100, 1), 50));
    result.add(std::make_unique<P>("focus", "Focus", R(0, 100, 1), 50));
    result.add(std::make_unique<P>("variation", "Variation", R(0, 100, 1), 50));
    result.add(std::make_unique<P>("richness", "Richness", R(0, 100, 1), 50));
    return result;
}

bool AruraMelodyProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
    const auto output = layouts.getMainOutputChannelSet();
    return output == juce::AudioChannelSet::mono() || output == juce::AudioChannelSet::stereo();
}

void AruraMelodyProcessor::prepareToPlay(double rate, int) { sampleRate = rate > 0 ? rate : 44100.0; }

template <typename Sample>
void AruraMelodyProcessor::render(juce::AudioBuffer<Sample>& audio, juce::MidiBuffer& midi)
{
    audio.clear();
    if (previewRequested.exchange(false)) { previewSeconds = 0; previewStopped = false; }
    if (previewStopped.load() || audio.getNumSamples() == 0) return;
    const juce::ScopedLock lock(midiLock);
    const auto end = previewSeconds + audio.getNumSamples() / sampleRate;
    for (int i = 0; i < sequence.getNumEvents(); ++i)
    {
        const auto message = sequence.getEventPointer(i)->message;
        const auto time = message.getTimeStamp();
        if (time >= previewSeconds && time < end)
            midi.addEvent(message, juce::jlimit(0, audio.getNumSamples() - 1,
                static_cast<int>((time - previewSeconds) * sampleRate)));
    }
    previewSeconds = end;
    if (sequence.getNumEvents() == 0 || previewSeconds > sequence.getEndTime() + 0.25) previewStopped = true;
}

void AruraMelodyProcessor::processBlock(juce::AudioBuffer<float>& a, juce::MidiBuffer& m) { render(a, m); }
void AruraMelodyProcessor::processBlock(juce::AudioBuffer<double>& a, juce::MidiBuffer& m) { render(a, m); }

void AruraMelodyProcessor::setGeneratedMidi(const juce::MemoryBlock& bytes)
{
    const juce::ScopedLock lock(midiLock); generatedMidi = bytes; rebuildSequence();
}

juce::MemoryBlock AruraMelodyProcessor::getGeneratedMidi() const
{
    const juce::ScopedLock lock(midiLock); return generatedMidi;
}

bool AruraMelodyProcessor::writeGeneratedMidi(const juce::File& file) const
{
    const auto bytes = getGeneratedMidi();
    return !bytes.isEmpty() && file.replaceWithData(bytes.getData(), bytes.getSize());
}

bool AruraMelodyProcessor::hasGeneratedMidi() const { return !getGeneratedMidi().isEmpty(); }
void AruraMelodyProcessor::startPreview() { previewRequested = true; }
void AruraMelodyProcessor::stopPreview() { previewStopped = true; }

void AruraMelodyProcessor::rebuildSequence()
{
    sequence.clear();
    juce::MemoryInputStream input(generatedMidi, false);
    juce::MidiFile file;
    if (!file.readFrom(input)) return;
    file.convertTimestampTicksToSeconds();
    for (int track = 0; track < file.getNumTracks(); ++track)
        if (const auto* source = file.getTrack(track))
            sequence.addSequence(*source, 0, 0, source->getEndTime() + 1);
    sequence.updateMatchedPairs();
}

void AruraMelodyProcessor::getStateInformation(juce::MemoryBlock& destination)
{
    auto snapshot = state.copyState();
    snapshot.setProperty("generatedMidi", getGeneratedMidi().toBase64Encoding(), nullptr);
    if (auto xml = snapshot.createXml()) copyXmlToBinary(*xml, destination);
}

void AruraMelodyProcessor::setStateInformation(const void* data, int size)
{
    if (auto xml = getXmlFromBinary(data, size); xml != nullptr && xml->hasTagName(state.state.getType()))
    {
        auto restored = juce::ValueTree::fromXml(*xml); state.replaceState(restored);
        juce::MemoryBlock bytes;
        if (bytes.fromBase64Encoding(restored.getProperty("generatedMidi").toString())) setGeneratedMidi(bytes);
    }
}

juce::AudioProcessorEditor* AruraMelodyProcessor::createEditor() { return new AruraMelodyEditor(*this); }
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new AruraMelodyProcessor(); }
