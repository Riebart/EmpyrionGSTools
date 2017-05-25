using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Net;
using System.Windows.Shapes;
using Microsoft.Win32;

namespace EGS_GUI
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {
        //public dynamic read_api_json(string url)
        //{
        //    HttpWebRequest request = (HttpWebRequest)HttpWebRequest.Create(url);
        //    request.UserAgent = "EmpyrionGSTools-GUI";
        //    WebResponse response = request.GetResponse();
        //    Stream rstream = response.GetResponseStream();
        //    string json = "";
        //    using (StreamReader sr = new StreamReader(rstream))
        //    {
        //        json = sr.ReadToEnd();
        //    }
        //    JavaScriptSerializer jss = new JavaScriptSerializer();
        //    dynamic o = jss.Deserialize<Dictionary<string, object>>(json);
        //    return o;
        //}

        public void check_release()
        {
            System.Diagnostics.Process proc = new System.Diagnostics.Process();
            proc.EnableRaisingEvents = true;
            proc.StartInfo.RedirectStandardOutput = true;
            proc.StartInfo.RedirectStandardError = true;
            proc.StartInfo.UseShellExecute = false;
            proc.StartInfo.CreateNoWindow = true;
            proc.StartInfo.FileName = ".\\lambda_index.exe";
            proc.StartInfo.Arguments = "--version-check";
            proc.Exited += VersionCheck_Exited;
            proc.Start();
        }

        bool version_compare(string v1, string v2)
        {
            // Because semantic versioning is only three points, and the MS versioning is four, 
            // add the missing component.
            try
            {
                Version ver1 = new Version(v1 + ".0");
                Version ver2 = new Version(v2 + ".0");
                int cmp = ver2.CompareTo(ver1);
                return (cmp > 0);
            }
            catch
            {
                return false;
            }
        }

        private void VersionCheck_Exited(object sender, EventArgs e)
        {
            System.Diagnostics.Process proc = (System.Diagnostics.Process)sender;
            string current_tag = proc.StandardOutput.ReadLine();
            string latest_tag = proc.StandardOutput.ReadLine();

            if ((latest_tag != "Unreleased") && version_compare(current_tag, latest_tag))
            {
                MessageBox.Show(
                    String.Format("Newer version available.\n\nCurrent version: {0}\nLatest version: {1}",
                    current_tag, latest_tag));
            }
        }

        public MainWindow()
        {
            InitializeComponent();
            hollowChk.IsChecked = true;
            morphChk.IsChecked = true;

            check_release();
        }

        String browse_filessytem(TextBox sender)
        {
            OpenFileDialog ofd = new OpenFileDialog();
            if (ofd.ShowDialog() == true)
            {
                sender.Text = ofd.FileName;
            }
            return "";
        }

        private void textBox1_Copy_MouseDoubleClick(object sender, MouseButtonEventArgs e)
        {
            browse_filessytem((TextBox)sender);
        }

        private void radioButton_Copy_Checked(object sender, RoutedEventArgs e)
        {
            RadioButton select_dim_radio = (RadioButton)sender;
            bool dim_state = (bool)select_dim_radio.IsChecked;
            xDimRadio.IsEnabled = dim_state;
            yDimRadio.IsEnabled = dim_state;
            zDimRadio.IsEnabled = dim_state;
        }

        private void morphChk_Checked(object sender, RoutedEventArgs e)
        {
            bool morph_state = (bool)((CheckBox)sender).IsChecked;
            erosionTxt.IsEnabled = morph_state;
            dilationTxt.IsEnabled = morph_state;
        }

        private void hollowChk_Checked(object sender, RoutedEventArgs e)
        {
            bool hollow_state = (bool)((CheckBox)sender).IsChecked;
            hollowTxt.IsEnabled = hollow_state;
        }

        private void Window_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            commandOutputTxt.Width = Math.Max(163, this.Width - commandOutputTxt.Margin.Left - 30);
            commandOutputTxt.Height = Math.Max(275, this.Height - commandOutputTxt.Margin.Top - 50);
        }

        private void runBtn_Click(object sender, RoutedEventArgs e)
        {
            System.Diagnostics.Process proc = new System.Diagnostics.Process();
            proc.EnableRaisingEvents = true;
            proc.ErrorDataReceived += Proc_ErrorDataReceived;
            proc.Exited += Proc_Exited;
            proc.StartInfo.RedirectStandardOutput = true;
            proc.StartInfo.RedirectStandardError = true;
            proc.StartInfo.UseShellExecute = false;
            proc.StartInfo.CreateNoWindow = true;

            proc.StartInfo.FileName = ".\\lambda_index.exe";
            string args = "";

            // Ensure that the input STL file exists.
            if (System.IO.File.Exists(stlInputTxt.Text))
            {
                args += "--stl-file=\"" + stlInputTxt.Text + "\"";
            }
            else
            {
                MessageBox.Show("STL Input file does not exist.");
                return;
            }

            args += " --blueprint-output-file=\"" + bpOutputTxt.Text + "\"";

            string bpClass = "";
            if (bpHV.IsChecked == true) { bpClass = "HV"; }
            if (bpSV.IsChecked == true) { bpClass = "SV"; }
            if (bpCV.IsChecked == true) { bpClass = "CV"; }
            if (bpBA.IsChecked == true) { bpClass = "BA"; }
            args += " --blueprint-class=" + bpClass;

            if (longestRad.IsChecked == true)
            {
                args += " --blueprint-size=" + bpSizeTxt.Text;
            }
            else if (specifiedRad.IsChecked == true)
            {
                args += " --blueprint-size=";
                if (xDimRadio.IsChecked == true) { args += "1"; }
                if (yDimRadio.IsChecked == true) { args += "2"; }
                if (zDimRadio.IsChecked == true) { args += "3"; }
                args += "," + bpSizeTxt.Text;
            }

            if (dimRemapTxt.Text != "") { args += " --dimension-remap=" + dimRemapTxt.Text; }
            if (dimMirrorTxt.Text != "") { args += " --dimension-mirror=" + dimMirrorTxt.Text; }
            
            if (morphChk.IsChecked == true)
            {
                args += " --morphological-factors=" + dilationTxt.Text + "," + erosionTxt.Text;
            }

            if (hollowChk.IsChecked == true)
            {
                args += " --hollow-radius=" + hollowTxt.Text;
            }

            if (nilReflectRadio.IsChecked == false)
            {
                args += " --reflect=";
                if (xReflectRadio.IsChecked == true) { args += "1"; }
                if (yReflectRadio.IsChecked == true) { args += "2"; }
                if (zReflectRadio.IsChecked == true) { args += "3"; }
            }

            if (smoothingChk.IsChecked == false) { args += " --disable-smoothing"; }

            proc.StartInfo.Arguments = args;
            commandOutputTxt.Text = "";
            proc.Start();
            proc.BeginErrorReadLine();
            runBtn.Content = "Running...";
            runBtn.IsEnabled = false;
            helpBtn.IsEnabled = false;
        }

        private void Proc_Exited(object sender, EventArgs e)
        {
            this.Dispatcher.Invoke(() =>
            {
                helpBtn.IsEnabled = true;
                runBtn.IsEnabled = true;
                runBtn.Content = "Run";
            });
        }

        private void Proc_ErrorDataReceived(object sender, System.Diagnostics.DataReceivedEventArgs e)
        {
            this.Dispatcher.Invoke(() =>
            {
                commandOutputTxt.Text += e.Data + "\n";
                commandOutputTxt.ScrollToEnd();
            });
        }

        private void helpBtn_Click(object sender, RoutedEventArgs e)
        {
            System.Diagnostics.Process proc = new System.Diagnostics.Process();
            proc.StartInfo.RedirectStandardOutput = true;
            proc.StartInfo.RedirectStandardError = true;
            proc.StartInfo.UseShellExecute = false;
            proc.StartInfo.CreateNoWindow = true;
            proc.StartInfo.FileName = ".\\lambda_index.exe";
            proc.StartInfo.Arguments = "--help";
            proc.Start();
            proc.WaitForExit();
            commandOutputTxt.Text = proc.StandardOutput.ReadToEnd();
        }
    }
}
