// Asterism - THE front door (owner: one exe, no "which do I click";
// a new user's first reflex in the folder is to look for
// "Asterism.exe"). Compiled by the csc.exe every Windows ships (see
// build-stub.ps1); the built exe lives at the repo ROOT and carries
// the asterism icon - the Desktop shortcut points here and inherits
// it.
//
// It does one thing and exits: run installer\launch.ps1 hidden, which
// routes - console up? open it; engine healthy? start the console;
// anything missing? open the setup page instead.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Program
{
    [STAThread]
    static void Main()
    {
        string here = Path.GetDirectoryName(Application.ExecutablePath);
        string launch = Path.Combine(here, "installer", "launch.ps1");
        if (!File.Exists(launch))
        {
            MessageBox.Show(
                "installer\\launch.ps1 was not found next to this file.\n" +
                "Keep Asterism.exe inside the Asterism folder.",
                "Asterism", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "powershell",
                Arguments = "-NoProfile -ExecutionPolicy Bypass " +
                            "-WindowStyle Hidden -File \"" + launch + "\"",
                WindowStyle = ProcessWindowStyle.Hidden,
                CreateNoWindow = true,
                UseShellExecute = false,
                WorkingDirectory = here,
            });
        }
        catch (Exception e)
        {
            MessageBox.Show(
                "Could not start Asterism: " + e.Message +
                "\n\nFallback: right-click installer\\launch.ps1 and" +
                " choose \"Run with PowerShell\".",
                "Asterism", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
