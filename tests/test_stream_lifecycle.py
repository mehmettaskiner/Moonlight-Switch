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
struct Session { bool is_terminated() { return false; } };
struct StreamingView {
    bool pendingSuspendTerminate = false, terminated = false;
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
    view.onWindowFocusChanged(false);
    view.onWindowFocusChanged(true); // waking before draw must not cancel pending stop
    view.draw();
    assert(view.stops == 1 && view.renders == 1 && !view.pendingSuspendTerminate);
    const int drops = input.drops;
    view.onWindowFocusChanged(false);
    assert(input.drops == drops && !view.pendingSuspendTerminate);
}
''')


if __name__ == '__main__':
    unittest.main()
