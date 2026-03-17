class Autokyo < Formula
  include Language::Python::Virtualenv

  desc "macOS local automation tool for page-by-page ebook viewer workflows"
  homepage "https://github.com/plain127/homebrew-autokyo"
  url "https://github.com/plain127/homebrew-autokyo/archive/refs/tags/v0.1.2.tar.gz"
  sha256 "31dae44c37d0fbf1706501bba0f5cce7877f64e2c09d1b48e35ae182da42c70c"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "autokyo", shell_output("#{bin}/autokyo --help")
  end
end
