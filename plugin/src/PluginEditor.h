#pragma once

#include <JuceHeader.h>
#include "PluginProcessor.h"

class AruraLookAndFeel final : public juce::LookAndFeel_V4
{
public:
    AruraLookAndFeel();
    void drawButtonBackground(juce::Graphics&, juce::Button&, const juce::Colour&, bool, bool) override;
    void drawRotarySlider(juce::Graphics&, int, int, int, int, float, float, float, juce::Slider&) override;
};

class AruraMelodyEditor final : public juce::AudioProcessorEditor,
                                private juce::FileDragAndDropTarget,
                                private juce::Timer
{
public:
    explicit AruraMelodyEditor(AruraMelodyProcessor&);
    ~AruraMelodyEditor() override;
    void paint(juce::Graphics&) override;
    void resized() override;

private:
    using Attachment = juce::AudioProcessorValueTreeState::SliderAttachment;
    AruraMelodyProcessor& processor;
    AruraLookAndFeel look;
    juce::Label title, subtitle, status, seedLabel, modelLabel, lengthLabel, tempoLabel;
    juce::Label welcome, welcomeDetail;
    juce::TextEditor endpoint;
    juce::ComboBox models, lengths;
    juce::Slider tempo;
    juce::TextButton connectButton { "CONNECT" }, loadButton { "LOAD" };
    juce::TextButton seedButton { "SEED MIDI" }, clearSeedButton { "CLEAR" };
    juce::TextButton generateButton { "G E N" }, playButton { "PLAY" };
    juce::TextButton stopButton { "STOP" }, saveButton { "G R A B" };
    juce::TextButton retryButton { "RETRY NOW" }, logButton { "OPEN LOG" };
    std::array<juce::Slider, 4> sliders;
    std::array<juce::Label, 4> labels;
    std::array<std::unique_ptr<Attachment>, 4> attachments;
    std::unique_ptr<juce::FileChooser> chooser;
    juce::File seedFile;
    int retryCount = 0;

    bool isInterestedInFileDrag(const juce::StringArray&) override;
    void filesDropped(const juce::StringArray&, int, int) override;
    void connect();
    void loadModel();
    void generate();
    void chooseSeed();
    void saveMidi();
    void useSeed(const juce::File&);
    void setBusy(bool, const juce::String&);
    void timerCallback() override;
    void showWelcome(bool, const juce::String& = {});
    void logMessage(const juce::String&) const;
    static juce::File logFile();
    juce::String baseUrl() const;
    juce::String selectedModel() const;
    static std::unique_ptr<juce::InputStream> request(const juce::URL&, const juce::String&, int&, int = 30000, bool = false);
    static juce::String errorFrom(const juce::var&, int);
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AruraMelodyEditor)
};
