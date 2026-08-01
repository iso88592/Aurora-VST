#pragma once

#include <JuceHeader.h>

class AruraMelodyProcessor final : public juce::AudioProcessor
{
public:
    AruraMelodyProcessor();
    void prepareToPlay(double, int) override;
    void releaseResources() override {}
    bool isBusesLayoutSupported(const BusesLayout&) const override;
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    void processBlock(juce::AudioBuffer<double>&, juce::MidiBuffer&) override;
    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }
    const juce::String getName() const override { return JucePlugin_Name; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return true; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*, int) override;

    void setGeneratedMidi(const juce::MemoryBlock&);
    juce::MemoryBlock getGeneratedMidi() const;
    bool writeGeneratedMidi(const juce::File&) const;
    bool hasGeneratedMidi() const;
    void startPreview();
    void stopPreview();
    juce::AudioProcessorValueTreeState state;

private:
    static juce::AudioProcessorValueTreeState::ParameterLayout makeParameters();
    template <typename Sample> void render(juce::AudioBuffer<Sample>&, juce::MidiBuffer&);
    void rebuildSequence();
    mutable juce::CriticalSection midiLock;
    juce::MemoryBlock generatedMidi;
    juce::MidiMessageSequence sequence;
    std::atomic<bool> previewRequested { false }, previewStopped { true };
    double sampleRate = 44100.0, previewSeconds = 0.0;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AruraMelodyProcessor)
};
