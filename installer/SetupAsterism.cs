// Setup Asterism - the double-clickable front door (owner: novices
// balk at .bat). ~30 lines, compiled by the csc.exe every Windows
// ships (see build-stub.ps1); the built exe lives at the repo ROOT
// as "Setup Asterism.exe" so it is the first thing in the folder.
//
// It does exactly two things and exits:
//   1. run installer\install.ps1 hidden (-FromStub: log + popups on
//      failure instead of a console)
//   2. open installer\welcome.html in the default browser - the page
//      polls localhost:8642 and becomes the Asterism console by
//      itself when the engine is up
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
        string ps1 = Path.Combine(here, "installer", "install.ps1");
        string welcome = Path.Combine(here, "installer", "welcome.html");
        if (!File.Exists(ps1))
        {
            MessageBox.Show(
                "installer\\install.ps1 was not found next to this file.\n" +
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
                            "-WindowStyle Hidden -File \"" + ps1 +
                            "\" -FromStub",
                WindowStyle = ProcessWindowStyle.Hidden,
                CreateNoWindow = true,
                UseShellExecute = false,
                WorkingDirectory = here,
            });
            Process.Start(new ProcessStartInfo
            {
                FileName = welcome,
                UseShellExecute = true,
            });
        }
        catch (Exception e)
        {
            MessageBox.Show(
                "Could not start the installer: " + e.Message +
                "\n\nFallback: double-click installer\\install.bat.",
                "Asterism", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
