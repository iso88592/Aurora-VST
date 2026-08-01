#include "PluginEditor.h"

namespace
{
constexpr auto defaultEndpoint = "http://localhost:8000/api/v1";
juce::String readAll(std::unique_ptr<juce::InputStream>& stream) { return stream ? stream->readEntireStreamAsString() : juce::String(); }
juce::var objectWith(std::initializer_list<std::pair<juce::Identifier, juce::var>> values)
{
    auto* object = new juce::DynamicObject;
    for (const auto& [key, value] : values) object->setProperty(key, value);
    return juce::var(object);
}

int scaleRootPitch(juce::String scale)
{
    scale = scale.trim().trimCharactersAtEnd("m");
    constexpr std::array roots { "A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#" };
    for (size_t i = 0; i < roots.size(); ++i)
        if (scale == roots[i]) return 57 + static_cast<int>(i);
    return 60;
}

bool writeScaleSeed(const juce::File& destination, const juce::String& scale)
{
    juce::MidiMessageSequence track;
    auto on = juce::MidiMessage::noteOn(1, scaleRootPitch(scale), static_cast<juce::uint8>(80)); on.setTimeStamp(0);
    auto off = juce::MidiMessage::noteOff(1, scaleRootPitch(scale)); off.setTimeStamp(480);
    track.addEvent(on); track.addEvent(off); track.updateMatchedPairs();
    juce::MidiFile midi; midi.setTicksPerQuarterNote(480); midi.addTrack(track);
    juce::FileOutputStream output(destination);
    return output.openedOk() && midi.writeTo(output);
}
}

AruraLookAndFeel::AruraLookAndFeel()
{
    const auto ink = juce::Colour(0xff30464d);
    setColour(juce::Label::textColourId, ink);
    setColour(juce::TextButton::textColourOffId, ink);
    setColour(juce::TextButton::textColourOnId, ink);
    setColour(juce::ComboBox::backgroundColourId, juce::Colour(0xfff4f7fa));
    setColour(juce::ComboBox::textColourId, ink);
    setColour(juce::ComboBox::outlineColourId, juce::Colour(0xff9baeb4));
    setColour(juce::PopupMenu::backgroundColourId, juce::Colour(0xfff4f7fa));
    setColour(juce::PopupMenu::textColourId, ink);
    setColour(juce::PopupMenu::highlightedBackgroundColourId, juce::Colour(0xff8de0d8));
    setColour(juce::PopupMenu::highlightedTextColourId, ink);
    setColour(juce::TextEditor::backgroundColourId, juce::Colour(0xfff4f7fa));
    setColour(juce::TextEditor::textColourId, ink);
    setColour(juce::TextEditor::highlightColourId, juce::Colour(0xff8de0d8));
    setColour(juce::TextEditor::outlineColourId, juce::Colour(0xff9baeb4));
    setColour(juce::Slider::textBoxTextColourId, ink);
    setColour(juce::Slider::textBoxBackgroundColourId, juce::Colour(0xfff4f7fa));
    setColour(juce::Slider::textBoxOutlineColourId, juce::Colours::transparentBlack);
    setColour(juce::Slider::thumbColourId, juce::Colour(0xff20c7c5));
    setColour(juce::Slider::trackColourId, juce::Colour(0xff20c7c5));
    setColour(juce::Slider::backgroundColourId, juce::Colour(0xffaebdc0));
}

void AruraLookAndFeel::drawButtonBackground(juce::Graphics& g, juce::Button& button, const juce::Colour&, bool hover, bool down)
{
    auto bounds = button.getLocalBounds().toFloat().reduced(1);
    const auto accent = button.getButtonText().contains("G E N") ? juce::Colour(0xff24c9cd) : juce::Colour(0xff9ba9ae);
    g.setColour(accent.brighter(hover ? 0.12f : 0.0f).darker(down ? 0.15f : 0.0f));
    g.fillRoundedRectangle(bounds, 8);
    g.setColour(juce::Colours::white.withAlpha(0.55f)); g.drawRoundedRectangle(bounds, 8, 1);
}

void AruraLookAndFeel::drawRotarySlider(juce::Graphics& g, int x, int y, int w, int h, float pos, float start, float end, juce::Slider&)
{
    auto bounds = juce::Rectangle<float>(x, y, w, h).reduced(12);
    const auto radius = juce::jmin(bounds.getWidth(), bounds.getHeight()) * 0.5f;
    const auto centre = bounds.getCentre();
    juce::ColourGradient body(juce::Colour(0xfff7fbfc), centre.x, centre.y - radius,
                              juce::Colour(0xffaebbc1), centre.x, centre.y + radius, false);
    g.setGradientFill(body); g.fillEllipse(bounds.withSizeKeepingCentre(radius * 2, radius * 2));
    g.setColour(juce::Colour(0xff839299)); g.drawEllipse(bounds.withSizeKeepingCentre(radius * 2, radius * 2), 1.5f);
    juce::Path arc; arc.addCentredArc(centre.x, centre.y, radius + 7, radius + 7, 0, start, start + pos * (end - start), true);
    g.setColour(juce::Colour(0xff19d6cf)); g.strokePath(arc, juce::PathStrokeType(4, juce::PathStrokeType::curved));
    const auto angle = start + pos * (end - start);
    juce::Path pointer; pointer.addRoundedRectangle(-1.5f, -radius * 0.65f, 3, radius * 0.38f, 1.5f);
    g.setColour(juce::Colour(0xff25c8d0)); g.fillPath(pointer, juce::AffineTransform::rotation(angle).translated(centre.x, centre.y));
}

AruraMelodyEditor::AruraMelodyEditor(AruraMelodyProcessor& owner) : AudioProcessorEditor(owner), processor(owner)
{
    setLookAndFeel(&look); setSize(600, 820);
    title.setText("AURORA", juce::dontSendNotification); title.setFont(juce::FontOptions(48, juce::Font::bold));
    title.setJustificationType(juce::Justification::centred); title.setColour(juce::Label::textColourId, juce::Colour(0xff8fa5af));
    subtitle.setText("MELODY GENERATOR", juce::dontSendNotification); subtitle.setFont(juce::FontOptions(17, juce::Font::bold));
    subtitle.setJustificationType(juce::Justification::centred); subtitle.setColour(juce::Label::textColourId, juce::Colour(0xff7d939d));
    endpoint.setText(processor.state.state.getProperty("endpoint", defaultEndpoint).toString());
    endpoint.setTextToShowWhenEmpty("Backend URL", juce::Colours::grey);
    status.setText("NO MODEL LOADED  •  READY", juce::dontSendNotification); status.setJustificationType(juce::Justification::centred);
    status.setColour(juce::Label::textColourId, juce::Colour(0xffbffef9));
    modelLabel.setText("MODEL", juce::dontSendNotification); lengthLabel.setText("LENGTH", juce::dontSendNotification);
    tempoLabel.setText("TEMPO", juce::dontSendNotification); scaleLabel.setText("SCALE", juce::dontSendNotification);
    seedLabel.setText("DROP MIDI SEED HERE", juce::dontSendNotification);
    seedLabel.setJustificationType(juce::Justification::centred);
    welcome.setText("WELCOME TO AURORA", juce::dontSendNotification);
    welcome.setFont(juce::FontOptions(25, juce::Font::bold)); welcome.setJustificationType(juce::Justification::centred);
    welcome.setColour(juce::Label::backgroundColourId, juce::Colour(0xffe7f2ef));
    welcome.setColour(juce::Label::textColourId, juce::Colour(0xff617880));
    welcomeDetail.setText("Starting safely. Checking the local Aurora API...", juce::dontSendNotification);
    welcomeDetail.setJustificationType(juce::Justification::centred); welcomeDetail.setMinimumHorizontalScale(0.7f);
    welcomeDetail.setColour(juce::Label::backgroundColourId, juce::Colour(0xffe7f2ef));
    welcomeDetail.setColour(juce::Label::textColourId, juce::Colour(0xff617880));
    lengths.addItem("SHORT", 80); lengths.addItem("MEDIUM", 150); lengths.addItem("LONG", 250);
    lengths.setSelectedId(static_cast<int>(processor.state.state.getProperty("length", 150)));
    constexpr std::array scaleNames { "Am", "A#m", "Bm", "Cm", "C#m", "Dm", "D#m", "Em", "Fm", "F#m", "Gm", "G#m",
                                      "A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#" };
    for (int i = 0; i < static_cast<int>(scaleNames.size()); ++i) scales.addItem(scaleNames[static_cast<size_t>(i)], i + 1);
    const auto storedScale = processor.state.state.getProperty("scale", "Cm").toString();
    auto scaleIndex = scales.getItemText(0).isNotEmpty() ? 0 : -1;
    for (int i = 0; i < scales.getNumItems(); ++i) if (scales.getItemText(i) == storedScale) scaleIndex = i;
    scales.setSelectedItemIndex(scaleIndex >= 0 ? scaleIndex : 3);
    tempo.setRange(60, 200, 1); tempo.setValue(static_cast<double>(processor.state.state.getProperty("tempo", 120.0)));
    tempo.setSliderStyle(juce::Slider::LinearHorizontal); tempo.setTextBoxStyle(juce::Slider::TextBoxRight, false, 75, 25); tempo.setTextValueSuffix(" BPM");

    for (auto* c : std::initializer_list<juce::Component*>{ &title, &subtitle, &status, &seedLabel, &modelLabel, &lengthLabel, &tempoLabel, &scaleLabel,
            &endpoint, &models, &lengths, &scales, &tempo, &connectButton, &loadButton, &seedButton, &clearSeedButton,
            &generateButton, &playButton, &stopButton, &saveButton, &welcome, &welcomeDetail, &retryButton, &logButton, &settingsButton }) addAndMakeVisible(c);
    constexpr std::array names { "CREATIVITY", "FOCUS", "VARIATION", "RICHNESS" };
    constexpr std::array ids { "creativity", "focus", "variation", "richness" };
    for (size_t i = 0; i < sliders.size(); ++i)
    {
        sliders[i].setSliderStyle(juce::Slider::RotaryHorizontalVerticalDrag);
        sliders[i].setTextBoxStyle(juce::Slider::TextBoxBelow, false, 64, 22); sliders[i].setTextValueSuffix("%");
        labels[i].setText(names[i], juce::dontSendNotification); labels[i].setJustificationType(juce::Justification::centred);
        labels[i].setColour(juce::Label::textColourId, juce::Colour(0xff82969f));
        attachments[i] = std::make_unique<Attachment>(processor.state, ids[i], sliders[i]);
        addAndMakeVisible(sliders[i]); addAndMakeVisible(labels[i]);
    }
    connectButton.onClick = [this] { connect(); }; loadButton.onClick = [this] { loadModel(); };
    generateButton.onClick = [this] { generate(); }; seedButton.onClick = [this] { chooseSeed(); };
    clearSeedButton.onClick = [this] { seedFile = juce::File(); seedLabel.setText("DROP MIDI SEED HERE", juce::dontSendNotification); };
    playButton.onClick = [this] { processor.startPreview(); status.setText("SENDING PREVIEW MIDI", juce::dontSendNotification); };
    stopButton.onClick = [this] { processor.stopPreview(); status.setText("PREVIEW STOPPED", juce::dontSendNotification); };
    saveButton.onClick = [this] { saveMidi(); };
    retryButton.onClick = [this] { retryCount = 0; connect(); };
    logButton.onClick = [] { logFile().startAsProcess(); };
    settingsButton.onClick = [this] { showSettings(!settingsVisible); };
    loadButton.setEnabled(false); generateButton.setEnabled(false);
    for (auto* b : { &playButton, &stopButton, &saveButton }) b->setEnabled(processor.hasGeneratedMidi());
    showSettings(false); showWelcome(true); logMessage("Plugin editor opened; backend-independent UI initialized"); startTimer(500);
}

AruraMelodyEditor::~AruraMelodyEditor()
{
    processor.state.state.setProperty("endpoint", endpoint.getText(), nullptr);
    processor.state.state.setProperty("length", lengths.getSelectedId(), nullptr);
    processor.state.state.setProperty("tempo", tempo.getValue(), nullptr);
    processor.state.state.setProperty("scale", scales.getText(), nullptr);
    processor.state.state.setProperty("model", selectedModel(), nullptr); setLookAndFeel(nullptr);
}

void AruraMelodyEditor::paint(juce::Graphics& g)
{
    juce::ColourGradient bg(juce::Colour(0xfff0faf7), 0, 0, juce::Colour(0xffdce9e5), 0, (float) getHeight(), false);
    g.setGradientFill(bg); g.fillAll(); g.setColour(juce::Colours::white.withAlpha(0.55f));
    g.fillRoundedRectangle(getLocalBounds().toFloat().reduced(12), 26);
    auto orb = juce::Rectangle<float>(190, 72, 220, 220);
    juce::ColourGradient glow(juce::Colour(0xffecfffa), orb.getCentreX(), orb.getY(), juce::Colour(0xff6d9790), orb.getCentreX(), orb.getBottom(), false);
    g.setGradientFill(glow); g.fillEllipse(orb); g.setColour(juce::Colours::white.withAlpha(0.8f)); g.drawEllipse(orb, 2);
    g.setColour(juce::Colour(0xff93a2a1)); g.fillRoundedRectangle(55, 340, 490, 80, 8);
    g.setColour(juce::Colour(0xffc7fff8)); g.setFont(juce::FontOptions(12, juce::Font::bold));
    g.drawText("MODEL", 70, 350, 80, 18, juce::Justification::left); g.drawText("STATUS", 70, 372, 80, 18, juce::Justification::left);
    g.drawText("OUTPUT", 70, 394, 80, 18, juce::Justification::left);
}

void AruraMelodyEditor::resized()
{
    title.setBounds(80, 130, 440, 70); subtitle.setBounds(120, 298, 360, 30); status.setBounds(150, 357, 380, 50);
    settingsButton.setBounds(455, 28, 90, 28);
    endpoint.setBounds(55, 435, 350, 30); connectButton.setBounds(415, 435, 130, 30);
    modelLabel.setBounds(55, 474, 55, 28); models.setBounds(110, 474, 300, 28); loadButton.setBounds(420, 474, 125, 28);
    seedLabel.setBounds(55, 440, 275, 32); seedButton.setBounds(336, 440, 125, 32); clearSeedButton.setBounds(468, 440, 77, 32);
    const int knobY = 490, knobW = 120;
    for (size_t i = 0; i < sliders.size(); ++i) { const int x = 45 + static_cast<int>(i) * 127; labels[i].setBounds(x, knobY, knobW, 22); sliders[i].setBounds(x, knobY + 18, knobW, 120); }
    scaleLabel.setBounds(55, 640, 55, 30); scales.setBounds(110, 640, 95, 30);
    tempoLabel.setBounds(215, 640, 55, 30); tempo.setBounds(270, 640, 130, 30); lengthLabel.setBounds(410, 640, 60, 30); lengths.setBounds(470, 640, 75, 30);
    playButton.setBounds(55, 748, 75, 36); stopButton.setBounds(137, 748, 75, 36); saveButton.setBounds(219, 748, 115, 36); generateButton.setBounds(346, 742, 199, 48);
    welcome.setBounds(75, 427, 450, 26); welcomeDetail.setBounds(75, 453, 450, 34);
    retryButton.setBounds(170, 490, 120, 30); logButton.setBounds(310, 490, 120, 30);
}

bool AruraMelodyEditor::isInterestedInFileDrag(const juce::StringArray& f) { return f.size() == 1 && (f[0].endsWithIgnoreCase(".mid") || f[0].endsWithIgnoreCase(".midi")); }
void AruraMelodyEditor::filesDropped(const juce::StringArray& f, int, int) { useSeed(juce::File(f[0])); }
void AruraMelodyEditor::useSeed(const juce::File& f) { seedFile = f; seedLabel.setText("SEED: " + f.getFileName(), juce::dontSendNotification); }
juce::String AruraMelodyEditor::baseUrl() const { return endpoint.getText().trim().trimCharactersAtEnd("/"); }
juce::String AruraMelodyEditor::selectedModel() const { return models.getText(); }

std::unique_ptr<juce::InputStream> AruraMelodyEditor::request(const juce::URL& url, const juce::String& headers, int& code, int timeout, bool multipart)
{
    const auto handling = multipart ? juce::URL::ParameterHandling::inPostData : juce::URL::ParameterHandling::inAddress;
    return url.createInputStream(juce::URL::InputStreamOptions(handling).withExtraHeaders(headers)
        .withConnectionTimeoutMs(timeout).withNumRedirectsToFollow(0).withStatusCode(&code));
}

juce::String AruraMelodyEditor::errorFrom(const juce::var& body, int code)
{
    if (const auto* o = body.getDynamicObject())
    {
        auto text = o->getProperty("detail").toString(); if (text.isEmpty()) text = o->getProperty("error").toString();
        if (text.isEmpty())
            if (const auto* errors = o->getProperty("errors").getArray(); errors != nullptr && !errors->isEmpty())
                text = errors->getReference(0).toString();
        if (text.isNotEmpty()) return text;
        const auto statusText = o->getProperty("status").toString();
        if (statusText.isNotEmpty() && statusText != "success") return "GENERATION " + statusText.toUpperCase();
    }
    if (code == 0) return "CONNECTION FAILED";
    if (code >= 200 && code < 300) return "REQUEST SUCCEEDED BUT RETURNED NO MIDI";
    return "HTTP " + juce::String(code);
}

void AruraMelodyEditor::setBusy(bool busy, const juce::String& text)
{
    for (auto* b : { &connectButton, &loadButton, &generateButton, &seedButton }) b->setEnabled(!busy);
    if (!busy) { loadButton.setEnabled(models.getNumItems() > 0); generateButton.setEnabled(models.getNumItems() > 0); }
    status.setText(text.toUpperCase(), juce::dontSendNotification);
}

juce::File AruraMelodyEditor::logFile()
{
    auto directory = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory).getChildFile("AruraMelody");
    directory.createDirectory();
    return directory.getChildFile("plugin.log");
}

void AruraMelodyEditor::logMessage(const juce::String& message) const
{
    logFile().appendText(juce::Time::getCurrentTime().toISO8601(true) + "  " + message + juce::newLine);
}

void AruraMelodyEditor::showWelcome(bool visible, const juce::String& detail)
{
    welcome.setVisible(visible); welcomeDetail.setVisible(visible); retryButton.setVisible(visible); logButton.setVisible(visible);
    if (visible)
    {
        for (auto* c : { static_cast<juce::Component*>(&seedLabel), static_cast<juce::Component*>(&seedButton), static_cast<juce::Component*>(&clearSeedButton) }) c->setVisible(false);
    }
    else if (!settingsVisible)
    {
        seedLabel.setVisible(true); seedButton.setVisible(true); clearSeedButton.setVisible(true);
    }
    if (detail.isNotEmpty()) welcomeDetail.setText(detail, juce::dontSendNotification);
    if (visible) { welcome.toFront(false); welcomeDetail.toFront(false); retryButton.toFront(false); logButton.toFront(false); }
}

void AruraMelodyEditor::showSettings(bool visible)
{
    settingsVisible = visible;
    for (auto* c : { static_cast<juce::Component*>(&endpoint), static_cast<juce::Component*>(&connectButton),
                     static_cast<juce::Component*>(&modelLabel), static_cast<juce::Component*>(&models), static_cast<juce::Component*>(&loadButton) })
        c->setVisible(visible);
    const auto showSeed = !visible && !welcome.isVisible();
    seedLabel.setVisible(showSeed); seedButton.setVisible(showSeed); clearSeedButton.setVisible(showSeed);
    settingsButton.setButtonText(visible ? "DONE" : "SETTINGS");
}

void AruraMelodyEditor::timerCallback()
{
    stopTimer(); connect();
}

void AruraMelodyEditor::connect()
{
    setBusy(true, "CONNECTING");
    showWelcome(true, "Checking " + baseUrl() + " — attempt " + juce::String(retryCount + 1) + " of 3");
    logMessage("Backend connection attempt " + juce::String(retryCount + 1) + ": " + baseUrl());
    const auto url = baseUrl() + "/models";
    juce::Thread::launch([safe = juce::Component::SafePointer<AruraMelodyEditor>(this), url]
    {
        int code = 0; auto stream = request(juce::URL(url), {}, code, 5000); auto json = juce::JSON::parse(readAll(stream)); juce::StringArray names;
        if (code >= 200 && code < 300) if (const auto* root = json.getDynamicObject())
            if (const auto* object = root->getProperty("models").getDynamicObject()) for (const auto& p : object->getProperties()) names.add(p.name.toString());
        juce::MessageManager::callAsync([safe, code, json, names]
        {
            if (!safe) return;
            safe->models.clear();
            for (int i = 0; i < names.size(); ++i) safe->models.addItem(names[i], i + 1);
            auto choice = names.indexOf(safe->processor.state.state.getProperty("model").toString()); if (choice < 0 && !names.isEmpty()) choice = 0;
            if (choice >= 0) safe->models.setSelectedItemIndex(choice);
            if (code >= 200 && code < 300)
            {
                safe->logMessage("Backend connected; discovered " + juce::String(names.size()) + " model(s)");
                safe->showWelcome(false); safe->setBusy(false, "CONNECTED • LOADING MODEL");
                if (!names.isEmpty()) safe->loadModel();
            }
            else
            {
                const auto reason = errorFrom(json, code);
                safe->logMessage("Backend connection failed: " + reason);
                ++safe->retryCount;
                if (safe->retryCount < 3)
                {
                    safe->showWelcome(true, reason + ". Retrying automatically in 2 seconds...");
                    safe->setBusy(false, reason); safe->startTimer(2000);
                }
                else
                {
                    safe->showWelcome(true, reason + ". Start the backend with python main.py, then retry.");
                    safe->setBusy(false, reason);
                }
            }
        });
    });
}

void AruraMelodyEditor::loadModel()
{
    if (selectedModel().isEmpty()) return;
    setBusy(true, "LOADING MODEL");
    logMessage("Loading model: " + selectedModel());
    const auto jsonText = juce::JSON::toString(objectWith({ { "model_name", selectedModel() }, { "force_reload", false } }));
    const auto url = juce::URL(baseUrl() + "/models/load").withPOSTData(jsonText);
    juce::Thread::launch([safe = juce::Component::SafePointer<AruraMelodyEditor>(this), url]
    {
        int code = 0; auto stream = request(url, "Content-Type: application/json\r\n", code); auto json = juce::JSON::parse(readAll(stream));
        juce::MessageManager::callAsync([safe, code, json]
        {
            if (!safe) return;
            const auto result = code >= 200 && code < 300 ? juce::String("MODEL LOADED • READY") : errorFrom(json, code);
            safe->logMessage("Model load result: " + result); safe->setBusy(false, result);
        });
    });
}

void AruraMelodyEditor::generate()
{
    if (selectedModel().isEmpty()) return;
    setBusy(true, seedFile.existsAsFile() ? "UPLOADING SEED • GENERATING" : "GENERATING");
    logMessage("Generation requested; model=" + selectedModel() + ", seed=" + (seedFile.existsAsFile() ? seedFile.getFileName() : "none"));
    const auto rootUrl = baseUrl();
    const auto model = selectedModel();
    const auto seed = seedFile;
    const auto maxLength = lengths.getSelectedId();
    const auto scale = scales.getText();
    const auto creativity = sliders[0].getValue(), focus = sliders[1].getValue(), variation = sliders[2].getValue(), richness = sliders[3].getValue(), bpm = tempo.getValue();
    juce::Thread::launch([safe = juce::Component::SafePointer<AruraMelodyEditor>(this), rootUrl, model, seed, scale, maxLength, creativity, focus, variation, richness, bpm]
    {
        auto effectiveSeed = seed;
        juce::File generatedScaleSeed;
        if (!effectiveSeed.existsAsFile())
        {
            generatedScaleSeed = juce::File::getSpecialLocation(juce::File::tempDirectory)
                                     .getNonexistentChildFile("AruraMelody-scale-seed", ".mid", false);
            if (writeScaleSeed(generatedScaleSeed, scale)) effectiveSeed = generatedScaleSeed;
        }
        auto params = objectWith({ { "temperature", 0.1 + creativity * 0.019 }, { "top_p", 0.1 + focus * 0.009 },
            { "repetition_penalty", 1.0 + variation * 0.01 }, { "top_k", juce::roundToInt(20 + richness * 0.8) }, { "max_length", maxLength } });
        juce::URL url(rootUrl + (effectiveSeed.existsAsFile() ? "/generate/from-midi" : "/generate")); juce::String headers;
        if (effectiveSeed.existsAsFile())
            url = url.withParameter("model_name", model).withParameter("params", juce::JSON::toString(params)).withParameter("num_generations", "1")
                     .withParameter("output_format", "vst_plugin").withParameter("max_seed_length", "50").withFileToUpload("midi_file", effectiveSeed, "audio/midi");
        else
        {
            juce::Array<juce::var> signature; signature.add(4); signature.add(4);
            auto body = objectWith({ { "model_name", model }, { "params", params }, { "num_generations", 1 }, { "output_format", "vst_plugin" }, { "tempo", bpm }, { "time_signature", signature } });
            url = url.withPOSTData(juce::JSON::toString(body)); headers = "Content-Type: application/json\r\n";
        }
        int code = 0; auto stream = request(url, headers, code, 300000, effectiveSeed.existsAsFile()); auto json = juce::JSON::parse(readAll(stream)); juce::MemoryBlock midi; int notes = 0; juce::String midiUrl;
        if (code >= 200 && code < 300) if (const auto* root = json.getDynamicObject()) if (const auto* melodies = root->getProperty("melodies").getArray(); melodies && !melodies->isEmpty())
            if (const auto* melody = melodies->getReference(0).getDynamicObject()) { midi.fromBase64Encoding(melody->getProperty("midi_base64").toString()); midiUrl = melody->getProperty("midi_url").toString(); if (const auto* n = melody->getProperty("notes").getArray()) notes = n->size(); }
        if (midi.isEmpty() && midiUrl.isNotEmpty())
        {
            auto downloadUrl = midiUrl;
            if (midiUrl.startsWithChar('/'))
            {
                const auto apiPosition = rootUrl.indexOf("/api/v1");
                downloadUrl = (apiPosition >= 0 ? rootUrl.substring(0, apiPosition) : rootUrl) + midiUrl;
            }
            int downloadCode = 0;
            auto download = request(juce::URL(downloadUrl), {}, downloadCode, 30000);
            if (downloadCode >= 200 && downloadCode < 300 && download != nullptr) download->readIntoMemoryBlock(midi);
        }
        if (generatedScaleSeed.existsAsFile()) generatedScaleSeed.deleteFile();
        juce::MessageManager::callAsync([safe, code, json, midi, notes]
        {
            if (!safe) return;
            if (!midi.isEmpty())
            {
                safe->processor.setGeneratedMidi(midi); for (auto* b : { &safe->playButton, &safe->stopButton, &safe->saveButton }) b->setEnabled(true);
                const auto result = "GENERATED " + juce::String(notes) + " NOTES"; safe->logMessage(result); safe->setBusy(false, result);
            }
            else { const auto result = errorFrom(json, code); safe->logMessage("Generation failed: " + result); safe->setBusy(false, result); }
        });
    });
}

void AruraMelodyEditor::chooseSeed()
{
    chooser = std::make_unique<juce::FileChooser>("Select MIDI seed", juce::File(), "*.mid;*.midi");
    chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
        [safe = juce::Component::SafePointer<AruraMelodyEditor>(this)](const juce::FileChooser& c) { if (safe && c.getResult().existsAsFile()) safe->useSeed(c.getResult()); });
}

void AruraMelodyEditor::saveMidi()
{
    chooser = std::make_unique<juce::FileChooser>("Save generated MIDI", juce::File::getSpecialLocation(juce::File::userDocumentsDirectory).getChildFile("Arura Melody.mid"), "*.mid");
    chooser->launchAsync(juce::FileBrowserComponent::saveMode | juce::FileBrowserComponent::warnAboutOverwriting,
        [safe = juce::Component::SafePointer<AruraMelodyEditor>(this)](const juce::FileChooser& c) { if (safe) safe->status.setText(safe->processor.writeGeneratedMidi(c.getResult()) ? "MIDI SAVED" : "SAVE FAILED", juce::dontSendNotification); });
}
