package com.buxin.employeetasks;

import android.app.Activity;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

public class MainActivity extends Activity {
    static final String HOME_URL = "https://buxin2.github.io/CEO/employee-signin.html";
    static final String ALLOWED_HOST = "buxin2.github.io";
    static final String ALLOWED_PATH = "/CEO/";

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setUserAgentString(settings.getUserAgentString() + " EmployeeTasksApp");

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, true);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !isAllowed(request.getUrl().toString());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return !isAllowed(url);
            }
        });

        webView.loadUrl(HOME_URL);
    }

    boolean isAllowed(String url) {
        if (url == null) return false;
        String lower = url.toLowerCase();
        if (lower.startsWith("about:") || lower.startsWith("data:")) return true;
        Uri uri = Uri.parse(url);
        String host = uri.getHost() == null ? "" : uri.getHost();
        String path = uri.getPath() == null ? "" : uri.getPath();
        if (!ALLOWED_HOST.equalsIgnoreCase(host) || !path.startsWith(ALLOWED_PATH)) {
            Toast.makeText(this, "This app is only for employee tasks.", Toast.LENGTH_SHORT).show();
            return false;
        }
        String page = path.substring(ALLOWED_PATH.length());
        if (page.contains("/") && !page.startsWith("css/") && !page.startsWith("js/") && !page.startsWith("img/") && !page.startsWith("data/")) {
            page = page.substring(page.lastIndexOf("/") + 1);
        }
        if (page.startsWith("login.html")
                || page.startsWith("dashboard.html")
                || page.startsWith("admin-")
                || page.startsWith("company.html")
                || page.startsWith("payments.html")
                || page.startsWith("ai-assistant.html")) {
            Toast.makeText(this, "This app is only for employee tasks.", Toast.LENGTH_SHORT).show();
            webView.loadUrl(HOME_URL);
            return false;
        }
        return true;
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        webView.loadUrl(HOME_URL);
    }
}
