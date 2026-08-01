cmake_minimum_required(VERSION 3.22)

project(AruraMelody VERSION 0.2.0 LANGUAGES C CXX)

include(FetchContent)
FetchContent_Declare(
  JUCE
  GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
  GIT_TAG 8.0.8
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(JUCE)

if(MSVC)
  set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

juce_add_plugin(AruraMelody
  COMPANY_NAME "Arura Labs"
  BUNDLE_ID com.aruralabs.aruramelody
  PLUGIN_MANUFACTURER_CODE Arur
  PLUGIN_CODE Aume
  FORMATS VST3 Standalone
  PRODUCT_NAME "Arura Melody"
  IS_SYNTH TRUE
  NEEDS_MIDI_INPUT TRUE
  NEEDS_MIDI_OUTPUT TRUE
  IS_MIDI_EFFECT FALSE
  COPY_PLUGIN_AFTER_BUILD FALSE
  VST3_CATEGORIES Instrument Generator
)

target_sources(AruraMelody PRIVATE
  src/PluginEditor.cpp
  src/PluginEditor.h
  src/PluginProcessor.cpp
  src/PluginProcessor.h
)

target_compile_features(AruraMelody PRIVATE cxx_std_20)
target_compile_definitions(AruraMelody PUBLIC
  JUCE_DISPLAY_SPLASH_SCREEN=0
  JUCE_REPORT_APP_USAGE=0
  JUCE_USE_CURL=1
  JUCE_WEB_BROWSER=0
  JUCE_VST3_CAN_REPLACE_VST2=0
)
target_link_libraries(AruraMelody PRIVATE
  juce::juce_audio_utils
  juce::juce_dsp
  PUBLIC
  juce::juce_recommended_config_flags
  juce::juce_recommended_lto_flags
  juce::juce_recommended_warning_flags
)

if(UNIX AND NOT APPLE)
  find_package(CURL REQUIRED)
  target_link_libraries(AruraMelody PRIVATE CURL::libcurl)
endif()

juce_generate_juce_header(AruraMelody)
