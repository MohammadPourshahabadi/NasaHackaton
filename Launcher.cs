using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Threading;
using System.Windows.Forms;

internal static class AboardLauncher
{
    [STAThread]
    private static int Main(string[] args)
    {
        bool smoke = args.Length == 1 && args[0] == "--smoke-test";
        try
        {
            using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("Aboard.Payload"))
            using (SHA256 sha = SHA256.Create())
            {
                if (payload == null) throw new InvalidOperationException("The application bundle is missing.");
                string version = BitConverter.ToString(sha.ComputeHash(payload)).Replace("-", "").Substring(0, 24);
                payload.Position = 0;
                string appData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string dataOverride = Environment.GetEnvironmentVariable("ABOARD_DATA_DIR");
                string cache = Path.Combine(smoke && !String.IsNullOrEmpty(dataOverride) ? dataOverride :
                    Path.Combine(appData, "Aboard"), "runtime-cache");
                string target = Path.Combine(cache, version);

                using (Mutex mutex = new Mutex(false, @"Local\AboardExtract-" + version))
                {
                    try { mutex.WaitOne(); } catch (AbandonedMutexException) { }
                    try
                    {
                        if (!File.Exists(Path.Combine(target, ".ready")))
                        {
                            Directory.CreateDirectory(cache);
                            string staging = Path.Combine(cache, Guid.NewGuid().ToString("N"));
                            Directory.CreateDirectory(staging);
                            try
                            {
                                using (ZipArchive zip = new ZipArchive(payload, ZipArchiveMode.Read))
                                {
                                    foreach (ZipArchiveEntry entry in zip.Entries)
                                    {
                                        if (String.IsNullOrEmpty(entry.Name)) continue;
                                        string destination = Path.GetFullPath(Path.Combine(staging, entry.FullName));
                                        if (!destination.StartsWith(staging + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                                            throw new InvalidDataException("Invalid application archive.");
                                        Directory.CreateDirectory(Path.GetDirectoryName(destination));
                                        entry.ExtractToFile(destination);
                                    }
                                }
                                File.WriteAllText(Path.Combine(staging, ".ready"), version);
                                Directory.Move(staging, target);
                            }
                            finally
                            {
                                if (Directory.Exists(staging)) Directory.Delete(staging, true);
                            }
                        }
                    }
                    finally { mutex.ReleaseMutex(); }
                }

                string runtime = Path.Combine(target, "runtime");
                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = Path.Combine(runtime, smoke ? "python.exe" : "pythonw.exe");
                start.Arguments = "-E -B -s \"" + Path.Combine(target, "desktop.py") + "\"" + (smoke ? " --smoke-test" : "");
                start.WorkingDirectory = target;
                start.UseShellExecute = false;
                start.CreateNoWindow = smoke;
                start.EnvironmentVariables["TCL_LIBRARY"] = Path.Combine(runtime, "tcl", "tcl8.6");
                start.EnvironmentVariables["TK_LIBRARY"] = Path.Combine(runtime, "tcl", "tk8.6");
                start.EnvironmentVariables["ABOARD_LAUNCH_DIR"] = AppDomain.CurrentDomain.BaseDirectory;
                using (Process process = Process.Start(start))
                {
                    process.WaitForExit();
                    return process.ExitCode;
                }
            }
        }
        catch (Exception error)
        {
            if (!smoke) MessageBox.Show(error.Message, "Aboard could not start", MessageBoxButtons.OK, MessageBoxIcon.Error);
            else Console.Error.WriteLine(error);
            return 1;
        }
    }
}
