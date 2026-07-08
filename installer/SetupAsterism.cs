// Setup Asterism - the double-clickable front door (owner: novices
// balk at .bat). ~30 lines, compiled by the csc.exe every Windows
// ships (see build-stub.ps1); the built exe lives at the repo ROOT
// as "Setup Asterism.exe" so it is the first thing in the folder.
//
// It does exactly two things and exits:
//   1. start installer\setup-server.ps1 hidden - a tiny local web
//      server that detects what's installed, takes the user's few
//      decisions, and installs every dependency (Python, engine, Git,
//      Lean, Claude Code, Mathlib) with live progress. NOT the engine:
//      the engine is just one thing it installs.
//   2. open the setup page in the default browser (http://127.0.0.1:
//      PORT/). When everything is ready the page hands off to the
//      Asterism console on :8642.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Program
{
    const int SetupPort = 8641;

    [STAThread]
    static void Main()
    {
        string here = Path.GetDirectoryName(Application.ExecutablePath);
        string server = Path.Combine(here, "installer", "setup-server.ps1");
        if (!File.Exists(server))
        {
            MessageBox.Show(
                "installer\\setup-server.ps1 was not found next to this file.\n" +
                "Keep Setup Asterism.exe inside the Asterism folder.",
                "Asterism", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "powershell",
                Arguments = "-NoProfile -ExecutionPolicy Bypass " +
                            "-WindowStyle Hidden -File \"" + server +
                            "\" " + SetupPort,
                WindowStyle = ProcessWindowStyle.Hidden,
                CreateNoWindow = true,
                UseShellExecute = false,
                WorkingDirectory = here,
            });
            // the page retries on its own until the server has bound,
            // so opening it immediately is fine
            Process.Start(new ProcessStartInfo
            {
                FileName = "http://127.0.0.1:" + SetupPort + "/",
                UseShellExecute = true,
            });
        }
        catch (Exception e)
        {
            MessageBox.Show(
                "Could not start the setup: " + e.Message +
                "\n\nFallback: right-click installer\\setup-server.ps1" +
                " and choose \"Run with PowerShell\", then open" +
                " http://127.0.0.1:" + SetupPort + "/ in your browser.",
                "Asterism", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
