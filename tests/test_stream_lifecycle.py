"""Exercise production C++ at external service boundaries, without Switch/GPU SDKs.

The harness extracts the unmodified function body, not a reimplementation. The
focus draw prefix ends before the renderer (which cannot run on the host).
A full Switch build separately checks the real SDK and class integration.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(path, signature):
    source = (ROOT / path).read_text()
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Production behavior missing: {signature}")
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def run_cpp(source):
    with tempfile.TemporaryDirectory() as tmp:
        cpp = Path(tmp) / 'test.cpp'
        binary = Path(tmp) / 'test'
        cpp.write_text(source)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-D__SWITCH__', '-Wall',
                        '-Wextra', '-fsanitize=address,undefined', str(cpp),
                        '-o', str(binary)], check=True, capture_output=True, text=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)


class LifecycleTests(unittest.TestCase):
    def test_focus_loss_disconnects_without_host_quit_before_rendering(self):
        callback = function('app/src/streaming_view.cpp',
                            'void StreamingView::onWindowFocusChanged(bool focused)')
        draw = function('app/src/streaming_view.cpp', 'void StreamingView::draw(')
        prefix = draw[draw.index('{') + 1:draw.index('session->draw(')]
        run_cpp(r'''
#include <cassert>
struct Logger { static void info(const char*) {} };
struct MoonlightInputManager {
    bool enabled = true; int drops = 0;
    static MoonlightInputManager& instance() { static MoonlightInputManager m; return m; }
    void setInputEnabled(bool value) { enabled = value; }
    void dropInput() { assert(!enabled); ++drops; }
};
struct Session {
    bool starting = false, disconnectRequested = false;
    bool is_terminated() { return false; }
    bool is_starting() { return starting; }
    void request_disconnect() { disconnectRequested = true; }
};
struct StreamingView {
    bool pendingSuspendTerminate = false, terminated = false;
    bool hostConnectionPending = false;
    int stops = 0, renders = 0;
    Session s; Session* session = &s;
    void onWindowFocusChanged(bool focused);
    void terminate(bool quit) { assert(!quit); ++stops; terminated = true; }
    void draw();
};
''' + callback + '\nvoid StreamingView::draw() {' + prefix + r'''
    ++renders;
}
int main() {
    auto& input = MoonlightInputManager::instance();
    StreamingView view;
    view.onWindowFocusChanged(true);
    assert(input.enabled && input.drops == 0 && !view.pendingSuspendTerminate);
    view.draw(); assert(view.renders == 1 && view.stops == 0);
    view.onWindowFocusChanged(false);
    assert(!input.enabled && input.drops == 1 && view.pendingSuspendTerminate);
    assert(view.stops == 0); // no teardown during event iteration
    view.hostConnectionPending = true;
    view.draw(); assert(view.stops == 0 && view.renders == 1);
    view.hostConnectionPending = false;
    view.s.starting = true;
    view.draw(); assert(view.stops == 0 && view.renders == 1);
    view.s.starting = false;
    view.onWindowFocusChanged(false);
    view.onWindowFocusChanged(true); // waking before draw must not cancel pending stop
    view.draw();
    assert(view.stops == 1 && view.renders == 1 && !view.pendingSuspendTerminate);
    const int drops = input.drops;
    view.onWindowFocusChanged(false);
    assert(input.drops == drops && !view.pendingSuspendTerminate);
}
''')


    def test_startup_guard_lasts_until_main_thread_completion(self):
        start = function('app/src/streaming/MoonlightSession.cpp', 'void MoonlightSession::start(')
        prefix = start[start.index('{') + 1:start.index('    m_is_sunshine')]
        run_cpp(r'''
#include <atomic>
#include <cassert>
#include <functional>
#include <vector>
template<class T> struct GSResult {
    bool ok;
    static GSResult failure(const char*) { return {false}; }
};
template<class T> using ServerCallback = const std::function<void(GSResult<T>)>;
namespace brls {
    std::vector<std::function<void()>> queue;
    void sync(std::function<void()> f) { queue.push_back(f); }
}
struct MoonlightSession {
    std::atomic<bool> m_disconnect_pending{false}, m_start_in_progress{false};
    std::function<void(GSResult<bool>)> workerCompletion;
    void start(ServerCallback<bool> callback, bool is_sunshine);
};
void MoonlightSession::start(ServerCallback<bool> callback, bool is_sunshine) {
    (void)is_sunshine;
''' + prefix + r'''
    workerCompletion = completeStart;
}
int main() {
    for (bool success : {false, true}) {
        MoonlightSession session; int calls=0;
        session.start([&](GSResult<bool> result) {
            assert(!session.m_start_in_progress);
            assert(result.ok==success); ++calls;
        }, true);
        assert(session.m_start_in_progress && calls==0);
        session.m_disconnect_pending=true;
        session.workerCompletion({success});
        assert(session.m_start_in_progress && calls==0);
        auto finish=brls::queue.back(); brls::queue.clear(); finish();
        assert(!session.m_start_in_progress && calls==1);
    }
    MoonlightSession stopped; stopped.m_disconnect_pending=true;
    int failures=0;
    stopped.start([&](GSResult<bool> result) { assert(!result.ok); ++failures; },true);
    assert(failures==1 && !stopped.m_start_in_progress && !stopped.workerCompletion);
    assert(brls::queue.empty());
}
''')

    def test_launch_and_resume_request_selected_mode_and_policy(self):
        start = function('app/src/libgamestream/client.cpp', 'int gs_start_app(')
        run_cpp(r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
constexpr int GS_OK=0, GS_IO_ERROR=-1, GS_NOT_SUPPORTED_4K=-2, GS_FAILED=-3;
constexpr int AUDIO_CONFIGURATION_STEREO=2, CHANNEL_COUNT_STEREO=2;
constexpr int CHANNEL_COUNT_51_SURROUND=6, CHANNEL_MASK_STEREO=3, CHANNEL_MASK_51_SURROUND=63;
constexpr int HTTPRequestTimeoutLong=30;
struct Data {
    char value[64] = "00112233445566778899aabbccddeeff00";
    static Data random_bytes(int) { return {}; }
    const char* bytes() const { return value; }
    Data hex() const { return {}; }
};
struct STREAM_CONFIGURATION {
    int width=1920, height=1080, fps=60, audioConfiguration=AUDIO_CONFIGURATION_STEREO;
    char remoteInputAesKey[16];
};
struct SERVER_DATA {
    bool supports4K=true; int currentGame=0; unsigned httpsPort=47984;
    struct { const char* address="127.0.0.1"; const char* rtspSessionUrl=nullptr; } serverInfo;
};
using PSERVER_DATA=SERVER_DATA*;
std::string unique_id="testclient", captured;
int transportResult=GS_OK, xmlResult=GS_OK;
void gs_set_error(const char*) {}
const char* LiGetLaunchUrlQueryParameters() { return "&testExtension=1"; }
int http_request(const char* url, Data*, int timeout) {
    assert(timeout==HTTPRequestTimeoutLong); captured=url; return transportResult;
}
int xml_status(const Data&) { return xmlResult; }
int xml_search(const Data&, const char* name, std::string* value) {
    *value = std::string(name)=="gamesession" ? "1" : "rtsp://test";
    return GS_OK;
}
namespace brls { struct Logger { static void error(const char*) {} }; }
''' + start + r'''
int main() {
    for (bool resume : {false,true}) for (bool sops : {false,true}) {
        for (int fps : {30,60,120}) for (int height : {720,1080,1440}) {
            SERVER_DATA server; server.currentGame=resume ? 42 : 0;
            STREAM_CONFIGURATION config;
            config.height=height; config.width=height*16/9; config.fps=fps;
            assert(gs_start_app(&server,&config,42,sops,true,3)==GS_OK);
            assert(captured.find(resume ? "/resume?" : "/launch?")!=std::string::npos);
            std::string mode="&mode="+std::to_string(config.width)+"x"+std::to_string(height)+"x"+std::to_string(sops && fps>60 ? 60 : fps);
            assert(captured.find(mode+"&")!=std::string::npos);
            assert(captured.find(sops ? "&sops=1&" : "&sops=0&")!=std::string::npos);
            assert(captured.find("uniqueid=testclient&")!=std::string::npos);
            assert(captured.find("&rikey=00112233445566778899aabbccddeeff00&rikeyid=0")!=std::string::npos);
            assert(captured.find("&testExtension=1")!=std::string::npos);
            if (!resume) {
                assert(captured.find("appid=42&")!=std::string::npos);
                assert(captured.find("&localAudioPlayMode=1&")!=std::string::npos);
                assert(captured.find("&remoteControllersBitmap=3&gcmap=3")!=std::string::npos);
            }
            assert(server.currentGame==42);
            delete[] server.serverInfo.rtspSessionUrl;
        }
    }
    SERVER_DATA server; STREAM_CONFIGURATION config;
    transportResult=GS_IO_ERROR;
    assert(gs_start_app(&server,&config,42,true,false,0)==GS_IO_ERROR);
    assert(server.currentGame==0);
    transportResult=GS_OK; server.supports4K=false; config.height=2160;
    captured.clear();
    assert(gs_start_app(&server,&config,42,true,false,0)==GS_NOT_SUPPORTED_4K);
    assert(captured.empty());
}
''')


if __name__ == '__main__':
    unittest.main()
